"""``MergeUpsert`` — insert new rows and update changed rows; no deletes.

Issues a per-row SELECT + INSERT or UPDATE to provide upsert semantics
without requiring a database-level MERGE statement, keeping the
implementation database-agnostic across the supported pool types.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class MergeUpsert(SubTapestry):
    """Insert new rows and update changed rows; never delete."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        non_key_columns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "MergeUpsert: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "MergeUpsert: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"MergeUpsert: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"MergeUpsert: key_columns and non_key_columns overlap "
                f"on {sorted(overlap)!r}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._non_key_columns = non_key_tuple
        self._all_columns = key_tuple + non_key_tuple
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

    async def process(self, **_: Any) -> dict[str, Any]:
        """Upsert source rows into target: insert new, update changed, skip deletes.

        Returns:
            A dict with keys ``succeeded``, ``target_table``,
            ``rows_inserted``, and ``rows_updated``.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        rows_inserted = 0
        rows_updated = 0
        for row in source_rows:
            row_dict = dict(zip(self._all_columns, row))
            key_values = tuple(row_dict[k] for k in self._key_columns)
            non_key_values = tuple(row_dict[k] for k in self._non_key_columns)
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
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
        }
