"""``FactTableLoad`` — Load fact rows with surrogate key resolution.

Resolves foreign-key surrogate keys for each incoming fact row by
looking up each dimension table.  When a natural key cannot be matched
in a dimension table, an "unknown" placeholder record is used
(late-arriving dimension handling).

Behaviour
---------
1. For each ``dim_lookups`` entry, look up the current surrogate key
   from the dimension table by the natural key values carried on the
   fact source row.
2. If no matching dimension row is found, substitute the configured
   ``unknown_sk`` value (default ``-1``).
3. Build the fact row by replacing the natural key columns with the
   resolved surrogate keys and write it to the fact table.

``dim_lookups`` is a sequence of :class:`DimLookupSpec` plain dicts with
the following keys:

* ``dim_table`` — target dimension table name
* ``dim_pool`` — pool to query (defaults to ``target_pool`` if omitted)
* ``natural_key_columns`` — sequence of column names in the source row
* ``surrogate_key_column`` — surrogate-key column name in the dim table
* ``fact_fk_column`` — column name to write the resolved SK into the fact row
* ``is_current_column`` — optional; if supplied, only rows where this column = 1
  are considered (Type 2 / Type 7 dimensions)
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class FactTableLoad(SubTapestry):
    """Load fact rows with surrogate-key lookup and late-arriving dimension handling."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        source_columns: Sequence[str],
        fact_columns: Sequence[str],
        dim_lookups: Sequence[dict[str, Any]],
        unknown_sk: int = -1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "FactTableLoad: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "FactTableLoad: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError(
                "FactTableLoad: source_query must be a non-empty string"
            )
        if not isinstance(target_table, str) or not target_table:
            raise ValueError(
                "FactTableLoad: target_table must be a non-empty string"
            )
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
            for key in ("dim_table", "natural_key_columns", "surrogate_key_column", "fact_fk_column"):
                if key not in spec:
                    raise ValueError(f"FactTableLoad: {label} missing key {key!r}")
            IdentifierValidator.validate_column(
                f"{label}.dim_table", spec["dim_table"]
            )
            IdentifierValidator.validate_column(
                f"{label}.surrogate_key_column", spec["surrogate_key_column"]
            )
            IdentifierValidator.validate_column(
                f"{label}.fact_fk_column", spec["fact_fk_column"]
            )
            nk_cols = tuple(spec["natural_key_columns"])
            IdentifierValidator.validate_columns(
                f"{label}.natural_key_columns", nk_cols
            )
            if "is_current_column" in spec and spec["is_current_column"] is not None:
                IdentifierValidator.validate_column(
                    f"{label}.is_current_column", spec["is_current_column"]
                )
            dim_pool = spec.get("dim_pool", None)
            if dim_pool is not None and not isinstance(
                dim_pool, DatabaseConnectionPool
            ):
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
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._source_columns = src_col_tuple
        self._fact_columns = fact_col_tuple
        self._dim_lookups = validated_lookups
        self._unknown_sk = unknown_sk
        super().__init__(_config=_config, **kwargs)

    def _build_dim_lookup_query(self, spec: dict[str, Any]) -> str:
        sk_col = spec["surrogate_key_column"]
        dim_table = spec["dim_table"]
        nk_cols = spec["natural_key_columns"]
        is_current = spec.get("is_current_column")
        where = " AND ".join(f"{c} = ?" for c in nk_cols)
        base = f"SELECT {sk_col} FROM {dim_table} WHERE {where}"
        if is_current:
            return f"{base} AND {is_current} = 1"
        return base

    def _build_insert_query(self, fk_columns: Sequence[str]) -> str:
        all_cols = list(self._fact_columns) + list(fk_columns)
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({col_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Resolve dimension surrogate keys for each source fact row and insert into the fact table.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, ``rows_inserted``,
            and ``late_arriving_count`` summarising the outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        fk_columns = [spec["fact_fk_column"] for spec in self._dim_lookups]
        insert_q = self._build_insert_query(fk_columns)
        rows_inserted = 0
        late_arriving_count = 0
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            fact_values = tuple(row_dict[c] for c in self._fact_columns)
            fk_values = []
            for spec in self._dim_lookups:
                pool = spec["dim_pool"] or self._target_pool
                lookup_q = self._build_dim_lookup_query(spec)
                nk_values = tuple(
                    row_dict[c] for c in spec["natural_key_columns"]
                )
                sk_rows = await pool.fetch_all(lookup_q, nk_values)
                if sk_rows:
                    fk_values.append(sk_rows[0][0])
                else:
                    fk_values.append(self._unknown_sk)
                    late_arriving_count += 1
            await self._target_pool.execute(
                insert_q, fact_values + tuple(fk_values)
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "late_arriving_count": late_arriving_count,
        }
