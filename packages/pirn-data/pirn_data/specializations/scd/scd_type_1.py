"""``ScdType1`` — Kimball Type 1 Slowly Changing Dimension (overwrite on change).

Type 1 replaces the existing target row's non-key columns whenever the source
row's values differ. No history is preserved — the previous attribute values are
lost. Use this for attributes where only the current value matters (a customer
name typo fix, a normalisation update).

For history-preserving SCD use :class:`~pirn_data.specializations.scd.scd_type_2.ScdType2`
(effective dating) or :class:`~pirn_data.specializations.scd.scd_type_7.ScdType7`
(surrogate key plus Type 2 history).

This is the *only* Type 1 implementation in the package. It previously had two
near-identical siblings — ``ScdType1MergeKnot``, which differed only in taking
its rows from an upstream knot, and ``MergeUpsert``, which differed only in
issuing a SELECT-then-UPDATE-or-INSERT per row instead of two set-based
statements. Both are deleted: ``rows`` is now an input here, and the set-based
statements are strictly fewer round trips for the same result.

Source rows arrive one of two ways, and exactly one must be given:

* ``rows`` — positional rows from an upstream knot, one value per
  ``column_names`` entry;
* ``source_pool`` + ``source_query`` — a query this knot runs itself.

Algorithm:
    1. Validate the pools, the table and column identifiers, and that
       ``primary_keys`` is a subset of ``column_names``.
    2. Materialise the source rows from ``rows`` or ``source_query``.
    3. Fetch every current target row; index it by primary key.
    4. Classify each source row: INSERT when its key is absent, UPDATE when a
       non-key value differs, skip when nothing changed.
    5. Inside one transaction on ``target_pool``, issue one ``execute_many`` for
       the inserts and one for the updates, so a failure part-way through
       leaves the dimension exactly as it was.
    6. Return ``succeeded``, ``target_table``, ``rows_inserted`` and
       ``rows_updated``.

References:
    [1] Kimball Group — SCD Type 1 (overwrite):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-1/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/connectors/database_connection_pool.py
    [3] pirn_data/pool_validator.py — the shared argument checks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.pool_validator import PoolValidator
from pirn_data.specializations.pool_merge_knot import PoolMergeKnot
from pirn_data.specializations.scd.scd_type_1_queries import ScdType1Queries


class ScdType1(PoolMergeKnot):
    """Perform a Type 1 SCD merge: overwrite changed rows, insert new rows."""

    def __init__(
        self,
        *,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        rows: Knot | Sequence[Sequence[Any]] | None = None,
        source_pool: Knot | DatabaseConnectionPool | None = None,
        source_query: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            target_pool=target_pool,
            target_table=target_table,
            primary_keys=primary_keys,
            column_names=column_names,
            rows=rows,
            source_pool=source_pool,
            source_query=source_query,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    async def _merge(
        source_rows: Sequence[tuple[Any, ...]],
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_key_tuple: tuple[str, ...],
        column_tuple: tuple[str, ...],
    ) -> dict[str, int]:
        """Classify ``source_rows`` against the target and apply the two statements."""
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        if not source_rows:
            return {"rows_inserted": 0, "rows_updated": 0}
        select_q = ScdType1Queries.select_query(target_table, column_tuple)
        insert_q = ScdType1Queries.insert_query(target_table, column_tuple)
        update_q = ScdType1Queries.update_query(target_table, primary_key_tuple, non_key_columns)
        existing_rows = await target_pool.fetch_all(select_q)
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key = ScdType1._index_rows_by_key(existing_rows, key_indices)
        inserts: list[tuple[Any, ...]] = []
        updates: list[tuple[Any, ...]] = []
        for row in source_rows:
            key = tuple(row[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append(row)
                continue
            existing = existing_by_key[key]
            if not ScdType1._non_key_values_changed(existing, row, non_key_indices):
                continue
            updates.append(tuple(row[i] for i in non_key_indices) + key)
        async with target_pool.transaction() as transaction:
            if inserts:
                await transaction.execute_many(insert_q, inserts)
            if updates and non_key_columns:
                await transaction.execute_many(update_q, updates)
        return {"rows_inserted": len(inserts), "rows_updated": len(updates)}

    async def process(
        self,
        *,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        rows: Any = None,
        source_pool: Any = None,
        source_query: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        PoolValidator.validate_pools("ScdType1", target_pool=target_pool)
        PoolValidator.validate_identifier("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        PoolValidator.validate_identifier("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        PoolValidator.validate_identifier("column_names", column_tuple)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType1: primary_keys not in column_names: {missing}")
        source_rows = await self._resolve_source_rows(
            "ScdType1", rows, source_pool, source_query, column_tuple
        )
        counts = await ScdType1._merge(
            source_rows, target_pool, target_table, primary_key_tuple, column_tuple
        )
        return {
            "succeeded": True,
            "target_table": target_table,
            **counts,
        }
