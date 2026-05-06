"""``ScdType1Overwrite`` — Slowly Changing Dimension Type 1 (overwrite).

SCD Type 1 keeps **only the current value** for every dimension row: when
a tracked attribute changes, the existing target row is updated in place
and history is lost. It is the right choice when the warehouse only
needs the latest snapshot (e.g. correcting a typo in a name) and storage
of historical states is not a regulatory or analytic requirement.

Behaviour
---------
For each row produced by ``source_query``:

* If a row with the same ``key_columns`` already exists in
  ``target_table``, ``UPDATE`` the ``non_key_columns`` to the new values.
* Otherwise ``INSERT`` a new row carrying both key and non-key columns.

The knot returns a primitive summary so pirn's content-addressing hash
does not have to walk a :class:`RunResult` whose outputs may contain a
:class:`DataBatch` with a type-bearing schema.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``key_columns``, and ``non_key_columns`` in
       ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and column disjointness.
    3. Fetch all rows from the source via ``source_pool.fetch_all``.
    4. For each row, issue a SELECT to check whether the key exists in the
       target table.
    5. If present, UPDATE the non-key columns; otherwise INSERT all columns.
    6. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_upserted``.

References:
    [1] Kimball Group — SCD Type 1 (overwrite):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-1/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType1Overwrite(Knot):
    """Upsert dimension rows in place, preserving no history (SCD Type 1)."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        non_key_columns: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            key_columns=key_columns,
            non_key_columns=non_key_columns,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _select_existing_query(target_table: str, key_columns: tuple[str, ...]) -> str:
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"SELECT 1 FROM {target_table} WHERE {where}"

    @staticmethod
    def _update_query(
        target_table: str,
        key_columns: tuple[str, ...],
        non_key_columns: tuple[str, ...],
    ) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where}"

    @staticmethod
    def _insert_query(target_table: str, all_columns: tuple[str, ...]) -> str:
        columns = ", ".join(all_columns)
        placeholders = ", ".join(["?"] * len(all_columns))
        return f"INSERT INTO {target_table} ({columns}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        key_columns: Any,
        non_key_columns: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ScdType1Overwrite: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType1Overwrite: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType1Overwrite: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("ScdType1Overwrite: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"ScdType1Overwrite: key_columns and non_key_columns overlap on {sorted(overlap)!r}"
            )
        all_columns = key_tuple + non_key_tuple
        source_rows = await source_pool.fetch_all(source_query)
        rows_upserted = 0
        for row in source_rows:
            row_dict = dict(zip(all_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            non_key_values = tuple(row_dict[k] for k in non_key_tuple)
            existing = await target_pool.fetch_all(
                ScdType1Overwrite._select_existing_query(target_table, key_tuple),
                key_values,
            )
            if existing:
                await target_pool.execute(
                    ScdType1Overwrite._update_query(target_table, key_tuple, non_key_tuple),
                    non_key_values + key_values,
                )
            else:
                await target_pool.execute(
                    ScdType1Overwrite._insert_query(target_table, all_columns),
                    key_values + non_key_values,
                )
            rows_upserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_upserted": rows_upserted,
        }
