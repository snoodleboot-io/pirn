"""``ScdType2`` — Kimball Type 2 Slowly Changing Dimension.

Type 2 ("add row on change") preserves a complete history of attribute
values by closing the current row (``valid_to = now()``,
``is_current = false``) and inserting a new effective-dated row with
the new attribute values. Queries can reconstruct any historical
attribute view by filtering on the effective date range or
``is_current``.

For history without surrogate keys use :class:`ScdType2`. For surrogate-
keyed history use :class:`ScdType7`.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``primary_keys``, ``column_names``, and optional
       date/flag column names in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier
       safety, pk ⊆ column_names, and no bookkeeping columns in column_names.
    3. Fetch all source rows via ``source_pool.fetch_all``.
    4. Delegate to ``ScdType2MergeKnot`` static helpers to classify and
       apply expiry + inserts.
    5. Return a summary dict with ``succeeded``, ``target_table``,
       ``rows_inserted``, and ``rows_expired``.

References:
    [1] Kimball Group — SCD Type 2 (add row):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.domains.data.specializations.scd.scd_type_2_merge_knot import ScdType2MergeKnot


class ScdType2(Knot):
    """Perform a Type 2 SCD merge: expire changed rows, insert new rows."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
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
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
    ) -> dict[str, int]:
        if not source_rows:
            return {"inserted": 0, "expired": 0}
        select_q = ScdType2MergeKnot._select_query(
            target_table, column_tuple, current_flag_column
        )
        insert_q = ScdType2MergeKnot._insert_query(
            target_table, column_tuple, effective_date_column,
            expiry_date_column, current_flag_column,
        )
        expire_q = ScdType2MergeKnot._expire_query(
            target_table, primary_key_tuple, expiry_date_column, current_flag_column
        )
        existing_rows = await target_pool.fetch_all(select_q)
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        for row in existing_rows:
            key = tuple(row[i] for i in key_indices)
            existing_by_key[key] = tuple(row)
        now = datetime.now(UTC).isoformat()
        inserts: list[tuple[Any, ...]] = []
        expires: list[tuple[Any, ...]] = []
        for row in source_rows:
            row_t = tuple(row)
            key = tuple(row_t[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append((*tuple(row_t), now, None, 1))
                continue
            existing = existing_by_key[key]
            if tuple(existing[i] for i in non_key_indices) == tuple(
                row_t[i] for i in non_key_indices
            ):
                continue
            expires.append((now, *key))
            inserts.append((*tuple(row_t), now, None, 1))
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
        effective_date_column: Any = "valid_from",
        expiry_date_column: Any = "valid_to",
        current_flag_column: Any = "is_current",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ScdType2: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType2: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType2: source_query must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        IdentifierValidator.validate_column("effective_date_column", effective_date_column)
        IdentifierValidator.validate_column("expiry_date_column", expiry_date_column)
        IdentifierValidator.validate_column("current_flag_column", current_flag_column)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType2: primary_keys not in column_names: {missing}")
        bookkeeping = (effective_date_column, expiry_date_column, current_flag_column)
        overlap = [c for c in bookkeeping if c in column_tuple]
        if overlap:
            raise ValueError(
                f"ScdType2: SCD bookkeeping columns must not appear in column_names: {overlap}"
            )
        source_rows = await source_pool.fetch_all(source_query)
        counts = await ScdType2._merge(
            source_rows,
            target_pool,
            target_table,
            primary_key_tuple,
            column_tuple,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        )
        return {
            "succeeded": True,
            "target_table": target_table,
            **counts,
        }
