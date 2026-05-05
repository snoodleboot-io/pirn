"""``ScdType7MergeKnot`` — surrogate-keyed Type 2 history merge for SCD Type 7.

Type 7 SCD (Kimball-style "hybrid surrogate-keyed history") keeps the
business key as a natural identifier and adds a surrogate key
(``scd_id``) that uniquely identifies each historical version. Each
inserted row receives a fresh surrogate id; queries that need the
current attribute values join through the surrogate, while history
queries filter on the effective-date range exactly as in Type 2.

This knot:

* Reads the existing current rows from the target
  (``current_flag_column = 1``).
* Closes (expires) any current row whose primary-key match has changed
  attributes.
* Inserts a new row for every changed-or-new primary key, allocating a
  fresh surrogate id (``MAX(scd_id) + 1`` for the batch).

Surrogate id allocation is per-merge, not per-row, so the column does
not need a database-managed sequence.

Algorithm:
    1. Receive resolved ``rows``, ``target_pool``, ``target_table``,
       ``primary_keys``, ``column_names``, surrogate/date/flag columns in
       ``process()``.
    2. Validate pool type, identifiers, pk ⊆ column_names, and no
       bookkeeping columns in column_names.
    3. Fetch current rows and query MAX surrogate key.
    4. Classify each source row: INSERT (new key) or EXPIRE+INSERT
       (changed non-key values). Allocate fresh surrogate ids.
    5. Bulk-execute expires, then bulk-execute inserts.
    6. Return a dict with ``inserted`` and ``expired`` counts.

References:
    [1] Kimball Group — SCD Type 7 (dual-type surrogate):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-7/
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


class ScdType7MergeKnot(Knot):
    """Merge a source row stream into a Type 7 surrogate-keyed target."""

    def __init__(
        self,
        *,
        rows: Knot,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        surrogate_key_column: Knot | str,
        effective_date_column: Knot | str,
        expiry_date_column: Knot | str,
        current_flag_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
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
    def _select_query(
        target_table: str, column_names: tuple[str, ...], current_flag_column: str
    ) -> str:
        column_list = ", ".join(column_names)
        return (
            f"SELECT {column_list} FROM {target_table} "
            f"WHERE {current_flag_column} = 1"
        )

    @staticmethod
    def _max_surrogate_query(
        target_table: str, surrogate_key_column: str
    ) -> str:
        return (
            f"SELECT COALESCE(MAX({surrogate_key_column}), 0) "
            f"FROM {target_table}"
        )

    @staticmethod
    def _insert_query(
        target_table: str,
        surrogate_key_column: str,
        column_names: tuple[str, ...],
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
    ) -> str:
        all_cols = [
            surrogate_key_column,
            *column_names,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        ]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def _expire_query(
        target_table: str,
        primary_keys: tuple[str, ...],
        expiry_date_column: str,
        current_flag_column: str,
    ) -> str:
        where_clause = " AND ".join(f"{k} = ?" for k in primary_keys)
        return (
            f"UPDATE {target_table} SET "
            f"{expiry_date_column} = ?, "
            f"{current_flag_column} = 0 "
            f"WHERE {where_clause} AND {current_flag_column} = 1"
        )

    async def process(
        self,
        *,
        rows: Any,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        surrogate_key_column: Any,
        effective_date_column: Any,
        expiry_date_column: Any,
        current_flag_column: Any,
        **_: Any,
    ) -> dict[str, int]:
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType7MergeKnot: target_pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        IdentifierValidator.validate_column("surrogate_key_column", surrogate_key_column)
        IdentifierValidator.validate_column("effective_date_column", effective_date_column)
        IdentifierValidator.validate_column("expiry_date_column", expiry_date_column)
        IdentifierValidator.validate_column("current_flag_column", current_flag_column)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(
                f"ScdType7MergeKnot: primary_keys not in column_names: {missing}"
            )
        bookkeeping = (
            surrogate_key_column,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        )
        overlap = [c for c in bookkeeping if c in column_tuple]
        if overlap:
            raise ValueError(
                "ScdType7MergeKnot: surrogate / effective / expiry / "
                f"current columns must not appear in column_names: {overlap}"
            )
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        materialised: list[tuple[Any, ...]] = [tuple(r) for r in rows]
        if not materialised:
            return {"inserted": 0, "expired": 0}
        select_q = ScdType7MergeKnot._select_query(
            target_table, column_tuple, current_flag_column
        )
        max_q = ScdType7MergeKnot._max_surrogate_query(target_table, surrogate_key_column)
        insert_q = ScdType7MergeKnot._insert_query(
            target_table,
            surrogate_key_column,
            column_tuple,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        )
        expire_q = ScdType7MergeKnot._expire_query(
            target_table, primary_key_tuple, expiry_date_column, current_flag_column
        )
        existing_rows = await target_pool.fetch_all(select_q)
        max_surrogate_rows = await target_pool.fetch_all(max_q)
        next_surrogate = int(max_surrogate_rows[0][0]) + 1 if max_surrogate_rows else 1
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        for row in existing_rows:
            key = tuple(row[i] for i in key_indices)
            existing_by_key[key] = tuple(row)
        now = datetime.now(UTC).isoformat()
        inserts: list[tuple[Any, ...]] = []
        expires: list[tuple[Any, ...]] = []
        for row in materialised:
            if len(row) != len(column_tuple):
                raise ValueError(
                    f"ScdType7MergeKnot: row width {len(row)} does not match "
                    f"column_names width {len(column_tuple)}"
                )
            key = tuple(row[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append((next_surrogate, *tuple(row), now, None, 1))
                next_surrogate += 1
                continue
            existing = existing_by_key[key]
            existing_non_keys = tuple(existing[i] for i in non_key_indices)
            new_non_keys = tuple(row[i] for i in non_key_indices)
            if existing_non_keys == new_non_keys:
                continue
            expires.append((now, *key))
            inserts.append((next_surrogate, *tuple(row), now, None, 1))
            next_surrogate += 1
        if expires:
            await target_pool.execute_many(expire_q, expires)
        if inserts:
            await target_pool.execute_many(insert_q, inserts)
        return {"inserted": len(inserts), "expired": len(expires)}
