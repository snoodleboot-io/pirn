"""``MergeUpsert`` — insert new rows and update changed rows; no deletes.

Issues a per-row SELECT + INSERT or UPDATE to provide upsert semantics
without requiring a database-level MERGE statement, keeping the
implementation database-agnostic across the supported pool types.

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
       ``rows_inserted``, and ``rows_updated``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class MergeUpsert(Knot):
    """Insert new rows and update changed rows; never delete."""

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
            raise TypeError("MergeUpsert: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("MergeUpsert: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("MergeUpsert: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("MergeUpsert: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"MergeUpsert: key_columns and non_key_columns overlap on {sorted(overlap)!r}"
            )
        all_columns = key_tuple + non_key_tuple
        source_rows = await source_pool.fetch_all(source_query)
        rows_inserted = 0
        rows_updated = 0
        for row in source_rows:
            row_dict = dict(zip(all_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            non_key_values = tuple(row_dict[k] for k in non_key_tuple)
            existing = await target_pool.fetch_all(
                MergeUpsert._select_existing_query(target_table, key_tuple),
                key_values,
            )
            if existing:
                await target_pool.execute(
                    MergeUpsert._update_query(target_table, key_tuple, non_key_tuple),
                    non_key_values + key_values,
                )
                rows_updated += 1
            else:
                await target_pool.execute(
                    MergeUpsert._insert_query(target_table, all_columns),
                    key_values + non_key_values,
                )
                rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
        }
