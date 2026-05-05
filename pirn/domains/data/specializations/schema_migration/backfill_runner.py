"""``BackfillRunner`` — runs a backfill query in configurable batch sizes.

Processes rows in batches keyed on a primary key column, tracking
progress and supporting resume from the last processed key.

Algorithm:
    1. Receive resolved ``source_pool``, ``target_pool``, ``source_table``,
       ``key_column``, ``batch_query_template``, ``batch_size``, and
       ``resume_from_key`` in ``process()``.
    2. Validate pool types, non-empty strings, identifier safety, and
       positive batch_size.
    3. Loop: execute ``batch_query_template`` with ``(last_key, batch_size)``
       until no rows are returned or a partial batch is received.
    4. For each batch, INSERT every row into ``source_table`` on
       ``target_pool`` using positional placeholders.
    5. Advance ``last_key`` to the first column of the last row.
    6. Return a summary dict with ``succeeded``, ``batches_processed``,
       ``rows_processed``, and ``last_processed_key``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class BackfillRunner(Knot):
    """Run a backfill query in batches with optional resume from last key."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        target_pool: Knot | DatabaseConnectionPool,
        source_table: Knot | str,
        key_column: Knot | str,
        batch_query_template: Knot | str,
        batch_size: Knot | int = 1000,
        resume_from_key: Knot | Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            target_pool=target_pool,
            source_table=source_table,
            key_column=key_column,
            batch_query_template=batch_query_template,
            batch_size=batch_size,
            resume_from_key=resume_from_key,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        source_pool: Any,
        target_pool: Any,
        source_table: Any,
        key_column: Any,
        batch_query_template: Any,
        batch_size: Any = 1000,
        resume_from_key: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Execute the backfill in batches, resuming from last_key if provided.

        Args:
            source_pool: DatabaseConnectionPool to read from.
            target_pool: DatabaseConnectionPool to write to.
            source_table: Table name for INSERT statements on target_pool.
            key_column: Primary key column name (used for ordering).
            batch_query_template: SQL with two positional params: last_key, limit.
            batch_size: Maximum rows per batch; must be a positive integer.
            resume_from_key: Key value to resume from (exclusive lower bound).

        Returns:
            A dict with keys ``succeeded``, ``batches_processed``,
            ``rows_processed``, and ``last_processed_key``.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("BackfillRunner: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("BackfillRunner: target_pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_table", source_table),
            ("batch_query_template", batch_query_template),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"BackfillRunner: {label} must be a non-empty string")
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("BackfillRunner: batch_size must be a positive integer")
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("key_column", key_column)

        last_key = resume_from_key
        batches_processed = 0
        rows_processed = 0
        while True:
            rows = await source_pool.fetch_all(
                batch_query_template,
                (last_key, batch_size),
            )
            if not rows:
                break
            for row in rows:
                col_count = len(row)
                placeholders = ", ".join(["?"] * col_count)
                insert_sql = f"INSERT INTO {source_table} VALUES ({placeholders})"
                await target_pool.execute(insert_sql, tuple(row))
            last_key = rows[-1][0]
            rows_processed += len(rows)
            batches_processed += 1
            if len(rows) < batch_size:
                break
        return {
            "succeeded": True,
            "batches_processed": batches_processed,
            "rows_processed": rows_processed,
            "last_processed_key": last_key,
        }
