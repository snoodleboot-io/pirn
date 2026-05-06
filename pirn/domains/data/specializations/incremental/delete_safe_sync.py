"""``DeleteSafeSync`` — full sync with soft-delete; never hard-deletes.

Synchronises a target table to match a source table's keyset by:

1. Extracting all key values from the source.
2. Comparing source keysets against the target.
3. Upserting rows present in source (insert new, update changed).
4. Soft-deleting rows in target that are absent from source by setting
   ``is_deleted = TRUE`` and ``deleted_at = now()``.

Hard deletes are never issued; rows removed from the source become
logically invisible via the ``is_deleted`` flag.

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows and build a set of source key tuples.
    3. For each source row, upsert into the target (SELECT + INSERT or UPDATE).
    4. Fetch all key tuples currently in the target.
    5. For each target key absent from the source keyset, issue a soft-delete
       UPDATE setting ``deleted_flag_column = 1`` and ``deleted_at_column = now``.
    6. Return a summary dict with ``rows_inserted``, ``rows_updated``, and
       ``rows_soft_deleted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class DeleteSafeSync(Knot):
    """Full table sync: upsert new/changed rows, soft-delete removed rows."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        non_key_columns: Knot | tuple[str, ...],
        deleted_flag_column: Knot | str = "is_deleted",
        deleted_at_column: Knot | str = "deleted_at",
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
            deleted_flag_column=deleted_flag_column,
            deleted_at_column=deleted_at_column,
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

    @staticmethod
    def _fetch_all_keys_query(target_table: str, key_columns: tuple[str, ...]) -> str:
        key_cols = ", ".join(key_columns)
        return f"SELECT {key_cols} FROM {target_table}"

    @staticmethod
    def _soft_delete_query(
        target_table: str,
        key_columns: tuple[str, ...],
        deleted_flag_column: str,
        deleted_at_column: str,
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return (
            f"UPDATE {target_table} "
            f"SET {deleted_flag_column} = 1, {deleted_at_column} = ? "
            f"WHERE {where}"
        )

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        key_columns: Any,
        non_key_columns: Any,
        deleted_flag_column: Any = "is_deleted",
        deleted_at_column: Any = "deleted_at",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("DeleteSafeSync: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("DeleteSafeSync: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("DeleteSafeSync: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("DeleteSafeSync: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("deleted_flag_column", deleted_flag_column)
        IdentifierValidator.validate_column("deleted_at_column", deleted_at_column)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"DeleteSafeSync: key_columns and non_key_columns overlap on {sorted(overlap)!r}"
            )
        all_columns = key_tuple + non_key_tuple
        now_iso = datetime.now(UTC).isoformat()
        source_rows = await source_pool.fetch_all(source_query)
        source_keysets: set[tuple[Any, ...]] = set()
        rows_inserted = 0
        rows_updated = 0
        for row in source_rows:
            row_dict = dict(zip(all_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            non_key_values = tuple(row_dict[k] for k in non_key_tuple)
            source_keysets.add(key_values)
            existing = await target_pool.fetch_all(
                DeleteSafeSync._select_existing_query(target_table, key_tuple),
                key_values,
            )
            if existing:
                await target_pool.execute(
                    DeleteSafeSync._update_query(target_table, key_tuple, non_key_tuple),
                    non_key_values + key_values,
                )
                rows_updated += 1
            else:
                await target_pool.execute(
                    DeleteSafeSync._insert_query(target_table, all_columns),
                    key_values + non_key_values,
                )
                rows_inserted += 1
        target_key_rows = await target_pool.fetch_all(
            DeleteSafeSync._fetch_all_keys_query(target_table, key_tuple)
        )
        rows_soft_deleted = 0
        for key_row in target_key_rows:
            key_values = tuple(key_row)
            if key_values not in source_keysets:
                await target_pool.execute(
                    DeleteSafeSync._soft_delete_query(
                        target_table, key_tuple, deleted_flag_column, deleted_at_column
                    ),
                    (now_iso, *key_values),
                )
                rows_soft_deleted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
            "rows_soft_deleted": rows_soft_deleted,
        }
