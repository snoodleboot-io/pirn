"""``ScdType7`` — Kimball Type 7 Slowly Changing Dimension.

Type 7 ("hybrid surrogate-keyed history") is the union of Type 1 and
Type 2 patterns: a surrogate key (``scd_id``) uniquely identifies each
historical version, and effective-date columns plus an ``is_current``
flag preserve the row-versioning history. Queries that want the
current attribute values join through the natural primary key with
``is_current = 1``; queries that want a snapshot at a point in time
filter on the effective-date range.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``primary_keys``, ``column_names``, and optional
       surrogate/date/flag column names in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier
       safety, pk ⊆ column_names, and no bookkeeping columns in column_names.
    3. Fetch all source rows via ``source_pool.fetch_all``.
    4. Build the statements with ``ScdType7Queries`` and classify,
       allocate surrogate ids, expire old rows, and insert new rows.
    5. Return a summary dict with ``succeeded``, ``target_table``,
       ``rows_inserted``, and ``rows_expired``.

References:
    [1] Kimball Group — SCD Type 7 (dual-type surrogate):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-7/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.specializations.pool_merge_knot import PoolMergeKnot
from pirn_data.specializations.scd.scd_type_7_queries import ScdType7Queries


class ScdType7(PoolMergeKnot):
    """Perform a Type 7 SCD merge: surrogate-keyed history with current-row flag."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        surrogate_key_column: Knot | str = "scd_id",
        effective_date_column: Knot | str = "valid_from",
        expiry_date_column: Knot | str = "valid_to",
        current_flag_column: Knot | str = "is_current",
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
            surrogate_key_column=surrogate_key_column,
            effective_date_column=effective_date_column,
            expiry_date_column=expiry_date_column,
            current_flag_column=current_flag_column,
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
        surrogate_key_column: str,
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
    ) -> dict[str, int]:
        if not source_rows:
            return {"inserted": 0, "expired": 0}
        select_q = ScdType7Queries.select_query(target_table, column_tuple, current_flag_column)
        max_q = ScdType7Queries.max_surrogate_query(target_table, surrogate_key_column)
        insert_q = ScdType7Queries.insert_query(
            target_table,
            surrogate_key_column,
            column_tuple,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
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
        for row in source_rows:
            row_t = tuple(row)
            key = tuple(row_t[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append((next_surrogate, *row_t, now, None, 1))
                next_surrogate += 1
                continue
            existing = existing_by_key[key]
            if not ScdType7._non_key_values_changed(existing, row_t, non_key_indices):
                continue
            expires.append((now, *key))
            inserts.append((next_surrogate, *row_t, now, None, 1))
            next_surrogate += 1
        if expires:
            await target_pool.execute_many(expire_q, expires)
        if inserts:
            await target_pool.execute_many(insert_q, inserts)
        return {"inserted": len(inserts), "expired": len(expires)}

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        surrogate_key_column: Any = "scd_id",
        effective_date_column: Any = "valid_from",
        expiry_date_column: Any = "valid_to",
        current_flag_column: Any = "is_current",
        **_: Any,
    ) -> dict[str, Any]:
        self._validate_pools("ScdType7", source_pool=source_pool, target_pool=target_pool)
        self._validate_non_empty_string("ScdType7", "source_query", source_query)
        self._validate_identifier("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        self._validate_identifier("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        self._validate_identifier("column_names", column_tuple)
        self._validate_identifier("surrogate_key_column", surrogate_key_column)
        self._validate_identifier("effective_date_column", effective_date_column)
        self._validate_identifier("expiry_date_column", expiry_date_column)
        self._validate_identifier("current_flag_column", current_flag_column)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType7: primary_keys not in column_names: {missing}")
        bookkeeping = (
            surrogate_key_column,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        )
        overlap = [c for c in bookkeeping if c in column_tuple]
        if overlap:
            raise ValueError(
                f"ScdType7: bookkeeping columns must not appear in column_names: {overlap}"
            )
        source_rows = await source_pool.fetch_all(source_query)
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
        )
        return {
            "succeeded": True,
            "target_table": target_table,
            **counts,
        }
