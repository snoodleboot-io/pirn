"""``ScdType1`` — Kimball Type 1 Slowly Changing Dimension.

Type 1 ("overwrite-on-change") replaces the existing target row's
non-key columns whenever the source row's values differ. No history is
preserved — the previous attribute values are lost. Use this for
attributes where only the current value matters (e.g. customer name
typo fix, normalisation update).

For history-preserving SCD use :class:`ScdType2` (effective dating) or
:class:`ScdType7` (surrogate key + Type 2 history).

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``primary_keys``, and ``column_names`` in
       ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier
       safety, and pk ⊆ column_names.
    3. Fetch all source rows via ``source_pool.fetch_all``.
    4. Fetch all current target rows; index by primary key.
    5. Classify each source row as INSERT (new key) or UPDATE (changed
       non-key values). Skip unchanged rows.
    6. Bulk-execute inserts and updates.
    7. Return a summary dict with ``succeeded``, ``target_table``,
       ``rows_inserted``, and ``rows_updated``.

References:
    [1] Kimball Group — SCD Type 1 (overwrite):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-1/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator
from pirn_data.specializations.scd.scd_type_1_merge_knot import ScdType1MergeKnot


class ScdType1(Knot):
    """Perform a Type 1 SCD merge: overwrite changed rows, insert new rows."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            primary_keys=primary_keys,
            column_names=column_names,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    async def _merge(
        source_rows: list[Any],
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_key_tuple: tuple[str, ...],
        column_tuple: tuple[str, ...],
    ) -> dict[str, int]:
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        if not source_rows:
            return {"inserted": 0, "updated": 0}
        select_q = ScdType1MergeKnot._select_query(target_table, column_tuple)
        insert_q = ScdType1MergeKnot._insert_query(target_table, column_tuple)
        update_q = ScdType1MergeKnot._update_query(target_table, primary_key_tuple, non_key_columns)
        existing_rows = await target_pool.fetch_all(select_q)
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        for row in existing_rows:
            key = tuple(row[i] for i in key_indices)
            existing_by_key[key] = tuple(row)
        inserts: list[tuple[Any, ...]] = []
        updates: list[tuple[Any, ...]] = []
        for row in source_rows:
            row_t = tuple(row)
            key = tuple(row_t[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append(row_t)
                continue
            existing = existing_by_key[key]
            if tuple(existing[i] for i in non_key_indices) == tuple(
                row_t[i] for i in non_key_indices
            ):
                continue
            updates.append(tuple(row_t[i] for i in non_key_indices) + key)
        if inserts:
            await target_pool.execute_many(insert_q, inserts)
        if updates and non_key_columns:
            await target_pool.execute_many(update_q, updates)
        return {"inserted": len(inserts), "updated": len(updates)}

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ScdType1: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType1: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType1: source_query must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType1: primary_keys not in column_names: {missing}")
        source_rows = await source_pool.fetch_all(source_query)
        counts = await ScdType1._merge(
            source_rows, target_pool, target_table, primary_key_tuple, column_tuple
        )
        return {
            "succeeded": True,
            "target_table": target_table,
            **counts,
        }
