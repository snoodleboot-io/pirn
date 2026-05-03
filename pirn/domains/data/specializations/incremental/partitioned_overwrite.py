"""``PartitionedOverwrite`` — atomically overwrites a single partition.

Deletes all existing rows for the specified partition key value and
re-inserts the source rows in their place. Other partitions are never
touched. This is appropriate for date-partitioned fact tables where each
pipeline run reprocesses exactly one partition.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class PartitionedOverwrite(SubTapestry):
    """Atomically overwrite a single partition of a partitioned table."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        partition_column: str,
        partition_value: Any,
        source_columns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "PartitionedOverwrite: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "PartitionedOverwrite: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"PartitionedOverwrite: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("partition_column", partition_column)
        column_tuple = tuple(source_columns)
        IdentifierValidator.validate_columns("source_columns", column_tuple)
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._partition_column = partition_column
        self._partition_value = partition_value
        self._source_columns = column_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def delete_query(self) -> str:
        return (
            f"DELETE FROM {self._target_table} "
            f"WHERE {self._partition_column} = ?"
        )

    @property
    def insert_query(self) -> str:
        columns = ", ".join(self._source_columns)
        placeholders = ", ".join(["?"] * len(self._source_columns))
        return (
            f"INSERT INTO {self._target_table} ({columns}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Delete the target partition then re-insert all source rows.

        Returns:
            A dict with keys ``succeeded``, ``target_table``,
            ``partition_column``, ``partition_value``, and ``rows_inserted``.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        await self._target_pool.execute(
            self.delete_query, (self._partition_value,)
        )
        rows_inserted = 0
        for row in source_rows:
            await self._target_pool.execute(self.insert_query, tuple(row))
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "partition_column": self._partition_column,
            "partition_value": self._partition_value,
            "rows_inserted": rows_inserted,
        }
