"""``PartitionedOverwrite`` — atomically overwrites a single partition.

Deletes all existing rows for the specified partition key value and
re-inserts the source rows in their place. Other partitions are never
touched. This is appropriate for date-partitioned fact tables where each
pipeline run reprocesses exactly one partition.

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all rows from the source via ``source_pool.fetch_all``.
    3. Issue a DELETE on the target for all rows where
       ``partition_column = partition_value``.
    4. INSERT each source row into the target.
    5. Return a summary dict with ``succeeded``, ``target_table``,
       ``partition_column``, ``partition_value``, and ``rows_inserted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class PartitionedOverwrite(Knot):
    """Atomically overwrite a single partition of a partitioned table."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        partition_column: Knot | str,
        partition_value: Knot | Any,
        source_columns: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            partition_column=partition_column,
            partition_value=partition_value,
            source_columns=source_columns,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _delete_query(target_table: str, partition_column: str) -> str:
        return f"DELETE FROM {target_table} WHERE {partition_column} = ?"

    @staticmethod
    def _insert_query(target_table: str, source_columns: tuple[str, ...]) -> str:
        columns = ", ".join(source_columns)
        placeholders = ", ".join(["?"] * len(source_columns))
        return f"INSERT INTO {target_table} ({columns}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        partition_column: Any,
        partition_value: Any,
        source_columns: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("PartitionedOverwrite: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("PartitionedOverwrite: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("PartitionedOverwrite: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("PartitionedOverwrite: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("partition_column", partition_column)
        column_tuple = tuple(source_columns)
        IdentifierValidator.validate_columns("source_columns", column_tuple)
        source_rows = await source_pool.fetch_all(source_query)
        await target_pool.execute(
            PartitionedOverwrite._delete_query(target_table, partition_column),
            (partition_value,),
        )
        rows_inserted = 0
        for row in source_rows:
            await target_pool.execute(
                PartitionedOverwrite._insert_query(target_table, column_tuple),
                tuple(row),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "partition_column": partition_column,
            "partition_value": partition_value,
            "rows_inserted": rows_inserted,
        }
