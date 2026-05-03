"""``DeleteSafeSync`` — full sync with soft-delete; never hard-deletes.

Synchronises a target table to match a source table's keyset by:

1. Extracting all key values from the source.
2. Comparing source keysets against the target.
3. Upserting rows present in source (insert new, update changed).
4. Soft-deleting rows in target that are absent from source by setting
   ``is_deleted = TRUE`` and ``deleted_at = now()``.

Hard deletes are never issued; rows removed from the source become
logically invisible via the ``is_deleted`` flag.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class DeleteSafeSync(SubTapestry):
    """Full table sync: upsert new/changed rows, soft-delete removed rows."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        non_key_columns: Sequence[str],
        deleted_flag_column: str = "is_deleted",
        deleted_at_column: str = "deleted_at",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "DeleteSafeSync: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DeleteSafeSync: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"DeleteSafeSync: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column(
            "deleted_flag_column", deleted_flag_column
        )
        IdentifierValidator.validate_column(
            "deleted_at_column", deleted_at_column
        )
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"DeleteSafeSync: key_columns and non_key_columns overlap "
                f"on {sorted(overlap)!r}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._non_key_columns = non_key_tuple
        self._all_columns = key_tuple + non_key_tuple
        self._deleted_flag_column = deleted_flag_column
        self._deleted_at_column = deleted_at_column
        super().__init__(_config=_config, **kwargs)

    @property
    def select_existing_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return f"SELECT 1 FROM {self._target_table} WHERE {where}"

    @property
    def update_query(self) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in self._non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return f"UPDATE {self._target_table} SET {set_clause} WHERE {where}"

    @property
    def insert_query(self) -> str:
        columns = ", ".join(self._all_columns)
        placeholders = ", ".join(["?"] * len(self._all_columns))
        return (
            f"INSERT INTO {self._target_table} ({columns}) "
            f"VALUES ({placeholders})"
        )

    @property
    def fetch_all_keys_query(self) -> str:
        key_cols = ", ".join(self._key_columns)
        return f"SELECT {key_cols} FROM {self._target_table}"

    @property
    def soft_delete_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return (
            f"UPDATE {self._target_table} "
            f"SET {self._deleted_flag_column} = 1, "
            f"{self._deleted_at_column} = ? "
            f"WHERE {where}"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Upsert all source rows and soft-delete rows absent from source.

        Returns:
            A dict with keys ``succeeded``, ``target_table``,
            ``rows_inserted``, ``rows_updated``, and ``rows_soft_deleted``.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        source_rows = await self._source_pool.fetch_all(self._source_query)
        source_keysets: set[tuple[Any, ...]] = set()
        rows_inserted = 0
        rows_updated = 0
        for row in source_rows:
            row_dict = dict(zip(self._all_columns, row))
            key_values = tuple(row_dict[k] for k in self._key_columns)
            non_key_values = tuple(row_dict[k] for k in self._non_key_columns)
            source_keysets.add(key_values)
            existing = await self._target_pool.fetch_all(
                self.select_existing_query, key_values
            )
            if existing:
                await self._target_pool.execute(
                    self.update_query, non_key_values + key_values
                )
                rows_updated += 1
            else:
                await self._target_pool.execute(
                    self.insert_query, key_values + non_key_values
                )
                rows_inserted += 1
        target_key_rows = await self._target_pool.fetch_all(
            self.fetch_all_keys_query
        )
        rows_soft_deleted = 0
        for key_row in target_key_rows:
            key_values = tuple(key_row)
            if key_values not in source_keysets:
                await self._target_pool.execute(
                    self.soft_delete_query, (now_iso,) + key_values
                )
                rows_soft_deleted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
            "rows_soft_deleted": rows_soft_deleted,
        }
