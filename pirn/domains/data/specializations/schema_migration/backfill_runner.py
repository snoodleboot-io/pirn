"""``BackfillRunner`` — runs a backfill query in configurable batch sizes.

Processes rows in batches keyed on a primary key column, tracking
progress and supporting resume from the last processed key.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class BackfillRunner(SubTapestry):
    """Run a backfill query in batches with optional resume from last key."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        target_pool: DatabaseConnectionPool,
        source_table: str,
        key_column: str,
        batch_query_template: str,
        batch_size: int = 1000,
        resume_from_key: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "BackfillRunner: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "BackfillRunner: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("batch_query_template", batch_query_template),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"BackfillRunner: {label} must be a non-empty string"
                )
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError(
                "BackfillRunner: batch_size must be a positive integer"
            )
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("key_column", key_column)
        self._source_pool = source_pool
        self._target_pool = target_pool
        self._source_table = source_table
        self._key_column = key_column
        self._batch_query_template = batch_query_template
        self._batch_size = batch_size
        self._resume_from_key = resume_from_key
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Execute the backfill in batches, resuming from last_key if provided.

        Iterates until no more rows are returned by the batch query. Each
        batch uses the last seen key value as the lower bound for the next
        batch.

        Returns:
            A dict with keys ``succeeded``, ``batches_processed``,
            ``rows_processed``, and ``last_processed_key``.
        """
        last_key = self._resume_from_key
        batches_processed = 0
        rows_processed = 0
        while True:
            rows = await self._source_pool.fetch_all(
                self._batch_query_template,
                (last_key, self._batch_size),
            )
            if not rows:
                break
            for row in rows:
                col_count = len(row)
                placeholders = ", ".join(["?"] * col_count)
                insert_sql = (
                    f"INSERT INTO {self._source_table} VALUES ({placeholders})"
                )
                await self._target_pool.execute(insert_sql, tuple(row))
            last_key = rows[-1][0]
            rows_processed += len(rows)
            batches_processed += 1
            if len(rows) < self._batch_size:
                break
        return {
            "succeeded": True,
            "batches_processed": batches_processed,
            "rows_processed": rows_processed,
            "last_processed_key": last_key,
        }
