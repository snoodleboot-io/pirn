"""``ScdType7`` — Kimball Type 7 Slowly Changing Dimension (dual current/historical view).

Type 7 is the dual-view dimension: a surrogate key (``scd_id``) identifies each
historical version, effective-date columns plus an ``is_current`` flag preserve
the Type 2 history, and — optionally — a set of ``current_*`` mirror columns
carry the latest value of each attribute on *every* row so a Type 1 "as is now"
query needs no join through the current row. A query wanting the current values
either filters ``is_current = 1`` or reads the mirror columns; a query wanting a
point-in-time snapshot filters on the effective-date range.

This is the *only* Type 7 implementation in the package. It previously had two
siblings: ``ScdType7MergeKnot``, which differed only in taking its rows from an
upstream knot, and ``ScdType7Hybrid``, which had no surrogate key at all (so it
was not Type 7) and whose one distinguishing feature — the ``current_*`` mirror
— is the ``current_columns`` input here. Both are deleted.

Source rows arrive one of two ways, and exactly one must be given:

* ``rows`` — positional rows from an upstream knot, one value per
  ``column_names`` entry;
* ``source_pool`` + ``source_query`` — a query this knot runs itself.

Algorithm:
    1. Validate the pools, identifiers, ``primary_keys ⊆ column_names``, that no
       bookkeeping column appears in ``column_names``, and — when
       ``current_columns`` is given — that it names a mirror column for every
       non-key column.
    2. Materialise the source rows from ``rows`` or ``source_query``.
    3. Read the current rows (``is_current = 1``) and the highest surrogate key.
    4. Classify each source row: INSERT when its key is absent, EXPIRE + INSERT
       when a non-key value changed, skip when nothing changed. Each insert
       takes the next surrogate key.
    5. Issue one ``execute_many`` for the expiries and one for the inserts, then
       — when mirroring — one backfill per changed key so every historical row
       carries the new current values.
    6. Return ``succeeded``, ``target_table``, ``rows_inserted`` and
       ``rows_expired``.

References:
    [1] Kimball Group — SCD Type 7 (dual type 1 and type 2 dimensions):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-7/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/connectors/database_connection_pool.py
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.pool_validator import PoolValidator
from pirn_data.specializations.pool_merge_knot import PoolMergeKnot
from pirn_data.specializations.scd.scd_type_7_queries import ScdType7Queries
from pirn_data.value_shape import ValueShape


class ScdType7(PoolMergeKnot):
    """Perform a Type 7 SCD merge: surrogate-keyed history with an optional current view."""

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
        surrogate_key_column: Knot | str = "scd_id",
        effective_date_column: Knot | str = "valid_from",
        expiry_date_column: Knot | str = "valid_to",
        current_flag_column: Knot | str = "is_current",
        current_columns: Knot | Mapping[str, str] | None = None,
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
            surrogate_key_column=surrogate_key_column,
            effective_date_column=effective_date_column,
            expiry_date_column=expiry_date_column,
            current_flag_column=current_flag_column,
            current_columns=current_columns,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _validate_current_columns(
        current_columns: Any, non_key_columns: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Check the mirror mapping and return the mirror column names in column order.

        Raises:
            TypeError: If ``current_columns`` is not a mapping.
            ValueError: If it does not name a mirror column for every non-key
                column.
        """
        if not ValueShape.is_mapping(current_columns):
            raise TypeError("ScdType7: current_columns must be a Mapping[str, str]")
        missing = [c for c in non_key_columns if c not in current_columns]
        if missing:
            raise ValueError(f"ScdType7: current_columns missing entries for {missing!r}")
        for source_column, mirror_column in current_columns.items():
            PoolValidator.validate_identifier(f"current_columns[{source_column!r}]", mirror_column)
        return tuple(current_columns[c] for c in non_key_columns)

    @staticmethod
    async def _merge(
        source_rows: Sequence[tuple[Any, ...]],
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_key_tuple: tuple[str, ...],
        column_tuple: tuple[str, ...],
        surrogate_key_column: str,
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
        mirror_columns: tuple[str, ...] | None,
    ) -> dict[str, int]:
        """Classify ``source_rows``, allocate surrogate keys, expire and insert."""
        if not source_rows:
            return {"rows_inserted": 0, "rows_expired": 0}
        select_q = ScdType7Queries.select_query(target_table, column_tuple, current_flag_column)
        max_q = ScdType7Queries.max_surrogate_query(target_table, surrogate_key_column)
        insert_q = ScdType7Queries.insert_query(
            target_table,
            surrogate_key_column,
            column_tuple,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
            mirror_columns,
        )
        expire_q = ScdType7Queries.expire_query(
            target_table, primary_key_tuple, expiry_date_column, current_flag_column
        )
        existing_rows = await target_pool.fetch_all(select_q)
        max_surrogate_rows = await target_pool.fetch_all(max_q)
        next_surrogate = int(max_surrogate_rows[0][0]) + 1 if max_surrogate_rows else 1
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key = ScdType7._index_rows_by_key(existing_rows, key_indices)
        now = datetime.now(UTC).isoformat()
        inserts: list[tuple[Any, ...]] = []
        expires: list[tuple[Any, ...]] = []
        backfills: list[tuple[Any, ...]] = []
        for row in source_rows:
            key = tuple(row[i] for i in key_indices)
            non_key_values = tuple(row[i] for i in non_key_indices)
            new_row: tuple[Any, ...] = (next_surrogate, *row, now, None, 1)
            if mirror_columns is not None:
                new_row = (*new_row, *non_key_values)
            if key not in existing_by_key:
                inserts.append(new_row)
                next_surrogate += 1
                continue
            existing = existing_by_key[key]
            if not ScdType7._non_key_values_changed(existing, row, non_key_indices):
                continue
            expires.append((now, *key))
            inserts.append(new_row)
            next_surrogate += 1
            if mirror_columns is not None:
                backfills.append(non_key_values + key)
        if expires:
            await target_pool.execute_many(expire_q, expires)
        if inserts:
            await target_pool.execute_many(insert_q, inserts)
        if backfills and mirror_columns is not None:
            backfill_q = ScdType7Queries.backfill_current_query(
                target_table, primary_key_tuple, mirror_columns
            )
            await target_pool.execute_many(backfill_q, backfills)
        return {"rows_inserted": len(inserts), "rows_expired": len(expires)}

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
        surrogate_key_column: Any = "scd_id",
        effective_date_column: Any = "valid_from",
        expiry_date_column: Any = "valid_to",
        current_flag_column: Any = "is_current",
        current_columns: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        PoolValidator.validate_pools("ScdType7", target_pool=target_pool)
        PoolValidator.validate_identifier("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        PoolValidator.validate_identifier("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        PoolValidator.validate_identifier("column_names", column_tuple)
        PoolValidator.validate_identifier("surrogate_key_column", surrogate_key_column)
        PoolValidator.validate_identifier("effective_date_column", effective_date_column)
        PoolValidator.validate_identifier("expiry_date_column", expiry_date_column)
        PoolValidator.validate_identifier("current_flag_column", current_flag_column)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType7: primary_keys not in column_names: {missing}")
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        mirror_columns = (
            None
            if current_columns is None
            else ScdType7._validate_current_columns(current_columns, non_key_columns)
        )
        bookkeeping = [
            surrogate_key_column,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
            *(mirror_columns or ()),
        ]
        overlap = [c for c in bookkeeping if c in column_tuple]
        if overlap:
            raise ValueError(
                f"ScdType7: bookkeeping columns must not appear in column_names: {overlap}"
            )
        source_rows = await self._resolve_source_rows(
            "ScdType7", rows, source_pool, source_query, column_tuple
        )
        counts = await ScdType7._merge(
            source_rows,
            target_pool,
            target_table,
            primary_key_tuple,
            column_tuple,
            surrogate_key_column,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
            mirror_columns,
        )
        return {
            "succeeded": True,
            "target_table": target_table,
            **counts,
        }
