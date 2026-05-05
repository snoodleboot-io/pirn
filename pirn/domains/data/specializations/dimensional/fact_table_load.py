"""``FactTableLoad`` — load fact rows with surrogate key resolution.

Resolves foreign-key surrogate keys for each incoming fact row by
looking up each dimension table.  When a natural key cannot be matched
in a dimension table, an "unknown" placeholder record is used
(late-arriving dimension handling).

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``source_columns``, ``fact_columns``,
       ``dim_lookups``, and ``unknown_sk`` in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and dim_lookups structure.
    3. Fetch all source rows.
    4. For each row look up each dimension's surrogate key via the configured
       ``natural_key_columns`` and ``surrogate_key_column``; substitute
       ``unknown_sk`` when no match is found.
    5. INSERT the fact row (fact columns + resolved FKs) into the target
       table.
    6. Return a summary dict with ``succeeded``, ``target_table``,
       ``rows_inserted``, and ``late_arriving_count``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class FactTableLoad(Knot):
    """Load fact rows with surrogate-key lookup and late-arriving dimension handling."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        source_columns: Knot | tuple[str, ...],
        fact_columns: Knot | tuple[str, ...],
        dim_lookups: Knot | Any,
        unknown_sk: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            source_columns=source_columns,
            fact_columns=fact_columns,
            dim_lookups=dim_lookups,
            unknown_sk=unknown_sk,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _build_dim_lookup_query(spec: dict[str, Any]) -> str:
        sk_col = spec["surrogate_key_column"]
        dim_table = spec["dim_table"]
        nk_cols = spec["natural_key_columns"]
        is_current = spec.get("is_current_column")
        where = " AND ".join(f"{c} = ?" for c in nk_cols)
        base = f"SELECT {sk_col} FROM {dim_table} WHERE {where}"
        if is_current:
            return f"{base} AND {is_current} = 1"
        return base

    @staticmethod
    def _build_insert_query(
        target_table: str,
        fact_columns: tuple[str, ...],
        fk_columns: list[str],
    ) -> str:
        all_cols = [*fact_columns, *fk_columns]
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({col_list}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        source_columns: Any,
        fact_columns: Any,
        dim_lookups: Any,
        unknown_sk: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("FactTableLoad: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("FactTableLoad: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("FactTableLoad: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("FactTableLoad: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        src_col_tuple = tuple(source_columns)
        fact_col_tuple = tuple(fact_columns)
        IdentifierValidator.validate_columns("source_columns", src_col_tuple)
        IdentifierValidator.validate_columns("fact_columns", fact_col_tuple)
        if not isinstance(dim_lookups, (list, tuple)) or not dim_lookups:
            raise ValueError("FactTableLoad: dim_lookups must be a non-empty sequence")
        validated_lookups = []
        for idx, spec in enumerate(dim_lookups):
            label = f"dim_lookups[{idx}]"
            if not isinstance(spec, dict):
                raise TypeError(f"FactTableLoad: {label} must be a dict")
            _required_keys = (
                "dim_table", "natural_key_columns", "surrogate_key_column", "fact_fk_column"
            )
            for key in _required_keys:
                if key not in spec:
                    raise ValueError(f"FactTableLoad: {label} missing key {key!r}")
            IdentifierValidator.validate_column(f"{label}.dim_table", spec["dim_table"])
            IdentifierValidator.validate_column(
                f"{label}.surrogate_key_column", spec["surrogate_key_column"]
            )
            IdentifierValidator.validate_column(
                f"{label}.fact_fk_column", spec["fact_fk_column"]
            )
            nk_cols = tuple(spec["natural_key_columns"])
            IdentifierValidator.validate_columns(f"{label}.natural_key_columns", nk_cols)
            if "is_current_column" in spec and spec["is_current_column"] is not None:
                IdentifierValidator.validate_column(
                    f"{label}.is_current_column", spec["is_current_column"]
                )
            dim_pool = spec.get("dim_pool", None)
            if dim_pool is not None and not isinstance(dim_pool, DatabaseConnectionPool):
                raise TypeError(
                    f"FactTableLoad: {label}.dim_pool must be a DatabaseConnectionPool"
                )
            validated_lookups.append(
                {
                    "dim_table": spec["dim_table"],
                    "natural_key_columns": nk_cols,
                    "surrogate_key_column": spec["surrogate_key_column"],
                    "fact_fk_column": spec["fact_fk_column"],
                    "is_current_column": spec.get("is_current_column"),
                    "dim_pool": dim_pool,
                }
            )
        fk_columns = [spec["fact_fk_column"] for spec in validated_lookups]
        insert_q = self._build_insert_query(target_table, fact_col_tuple, fk_columns)
        source_rows = await source_pool.fetch_all(source_query)
        rows_inserted = 0
        late_arriving_count = 0
        for row in source_rows:
            row_dict = dict(zip(src_col_tuple, row, strict=False))
            fact_values = tuple(row_dict[c] for c in fact_col_tuple)
            fk_values = []
            for spec in validated_lookups:
                pool = spec["dim_pool"] or target_pool
                lookup_q = self._build_dim_lookup_query(spec)
                nk_values = tuple(row_dict[c] for c in spec["natural_key_columns"])
                sk_rows = await pool.fetch_all(lookup_q, nk_values)
                if sk_rows:
                    fk_values.append(sk_rows[0][0])
                else:
                    fk_values.append(unknown_sk)
                    late_arriving_count += 1
            await target_pool.execute(insert_q, (*fact_values, *fk_values))
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "late_arriving_count": late_arriving_count,
        }
