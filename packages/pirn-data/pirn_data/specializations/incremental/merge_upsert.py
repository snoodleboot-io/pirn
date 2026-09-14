"""``MergeUpsert`` — insert new rows and update changed rows; no deletes.

Issues a per-row SELECT + INSERT or UPDATE to provide upsert semantics
without requiring a database-level MERGE statement, keeping the
implementation database-agnostic across the supported pool types.

This is also the SCD Type 1 (overwrite, no history) upsert pattern; use
this class for that rather than
:class:`~pirn_data.specializations.scd.scd_type_1_overwrite.ScdType1Overwrite`,
which is deprecated (PIR-870) — it duplicated this exact select/update/insert
logic under a separate name. The two differ only in what the summary dict
reports: this class splits ``rows_inserted`` / ``rows_updated`` where
``ScdType1Overwrite`` reports a single combined ``rows_upserted``.

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
        pirn/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.specializations._pool_merge_knot import _PoolMergeKnot


class MergeUpsert(_PoolMergeKnot):
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
        self._validate_pools("MergeUpsert", source_pool=source_pool, target_pool=target_pool)
        self._validate_non_empty_string("MergeUpsert", "source_query", source_query)
        self._validate_non_empty_string("MergeUpsert", "target_table", target_table)
        self._validate_identifier("target_table", target_table)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        self._validate_identifier("key_columns", key_tuple)
        self._validate_identifier("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"MergeUpsert: key_columns and non_key_columns overlap on {sorted(overlap)!r}"
            )
        source_rows = await source_pool.fetch_all(source_query)
        matched = await self._execute_per_row_upsert(
            source_rows,
            target_pool,
            key_tuple,
            non_key_tuple,
            MergeUpsert._select_existing_query(target_table, key_tuple),
            MergeUpsert._update_query(target_table, key_tuple, non_key_tuple),
            MergeUpsert._insert_query(target_table, key_tuple + non_key_tuple),
        )
        rows_updated = sum(matched)
        rows_inserted = len(matched) - rows_updated
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
        }
