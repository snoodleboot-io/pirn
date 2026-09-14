"""``ScdType1MergeKnot`` — overwrite-on-change merge for SCD Type 1.

Reads source rows and existing target rows in one knot, classifies each
source row as INSERT (key absent in target) or UPDATE (key present in
target with at least one changed value), and issues the corresponding
parameterised statements through the target pool.

Type 1 SCD (Kimball-style "overwrite") preserves no history: an updated
attribute simply replaces the previous value. For history-preserving
behaviour use :class:`ScdType2MergeKnot` (Type 2) or
:class:`ScdType7MergeKnot` (Type 7).

Algorithm:
    1. Receive resolved ``rows``, ``target_pool``, ``target_table``,
       ``primary_keys``, and ``column_names`` in ``process()``.
    2. Validate pool type, identifier safety, and pk ⊆ column_names.
    3. Fetch all current rows from the target table.
    4. Index existing rows by their primary key tuple.
    5. Classify each source row as INSERT (key absent) or UPDATE (key
       present with any non-key column changed). Skip unchanged rows.
    6. Bulk-execute inserts via ``execute_many``, then bulk-execute
       updates via ``execute_many``.
    7. Return a dict with ``inserted`` and ``updated`` counts.

References:
    [1] Kimball Group — SCD Type 1 (overwrite):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-1/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.specializations.pool_merge_knot import PoolMergeKnot
from pirn_data.specializations.scd.scd_type_1_queries import ScdType1Queries


class ScdType1MergeKnot(PoolMergeKnot):
    """Merge a source row stream into a target table by overwriting on change."""

    def __init__(
        self,
        *,
        rows: Knot,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            target_pool=target_pool,
            target_table=target_table,
            primary_keys=primary_keys,
            column_names=column_names,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        rows: Any,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        **_: Any,
    ) -> dict[str, int]:
        self._validate_pools("ScdType1MergeKnot", target_pool=target_pool)
        self._validate_identifier("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        self._validate_identifier("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        self._validate_identifier("column_names", column_tuple)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType1MergeKnot: primary_keys not in column_names: {missing}")
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        materialised: list[tuple[Any, ...]] = [tuple(r) for r in rows]
        if not materialised:
            return {"inserted": 0, "updated": 0}
        select_q = ScdType1Queries.select_query(target_table, column_tuple)
        insert_q = ScdType1Queries.insert_query(target_table, column_tuple)
        update_q = ScdType1Queries.update_query(target_table, primary_key_tuple, non_key_columns)
        existing_rows = await target_pool.fetch_all(select_q)
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key = ScdType1MergeKnot._index_rows_by_key(existing_rows, key_indices)
        inserts: list[tuple[Any, ...]] = []
        updates: list[tuple[Any, ...]] = []
        for row in materialised:
            self._validate_row_width("ScdType1MergeKnot", row, column_tuple)
            key = tuple(row[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append(row)
                continue
            existing = existing_by_key[key]
            if not ScdType1MergeKnot._non_key_values_changed(existing, row, non_key_indices):
                continue
            updates.append(tuple(row[i] for i in non_key_indices) + key)
        if inserts:
            await target_pool.execute_many(insert_q, inserts)
        if updates and non_key_columns:
            await target_pool.execute_many(update_q, updates)
        return {"inserted": len(inserts), "updated": len(updates)}
