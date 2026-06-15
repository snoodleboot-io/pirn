"""``AppendOnlyIngest`` — insert rows from a source query into a target
table without truncation, dedup, or watermarking.

Use this when:
- The source produces only new rows since the previous run (e.g. event
  log, audit trail, append-only fact table at the source).
- You manage idempotency via primary keys / unique constraints at the
  target rather than via watermark logic.

For source datasets that may re-emit older rows on each run, use
:class:`pirn_data.specializations.ingestion.watermark_incremental_extract.WatermarkIncrementalExtract`
instead — this knot will happily insert duplicates if the source does.

Algorithm:
    1. Receive ``source_pool``, ``source_query``, ``target_pool``, and
       ``insert_query`` in ``process()``.
    2. Validate pool types and non-empty query strings.
    3. Fetch all source rows via ``source_pool.fetch_all``.
    4. Insert the rows into the target via ``target_pool.execute_many``.
    5. Return a summary dict with ``succeeded``, ``rows_inserted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class AppendOnlyIngest(Knot):
    """Read all rows from a source query and append them to a target table."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        insert_query: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            insert_query=insert_query,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        insert_query: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Validate inputs, fetch source rows, insert into target, return summary.

        Args:
            source_pool: Pool to read rows from.
            source_query: SELECT query to execute against the source.
            target_pool: Pool to write rows to.
            insert_query: INSERT query to execute for each row batch.

        Returns:
            A dict with ``succeeded`` and ``rows_inserted``.

        Raises:
            TypeError: If either pool is not a ``DatabaseConnectionPool``.
            ValueError: If either query is empty.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("AppendOnlyIngest: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("AppendOnlyIngest: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("AppendOnlyIngest: source_query must be a non-empty string")
        if not isinstance(insert_query, str) or not insert_query:
            raise ValueError("AppendOnlyIngest: insert_query must be a non-empty string")
        rows = await source_pool.fetch_all(source_query)
        await target_pool.execute_many(insert_query, [tuple(r) for r in rows])
        return {"succeeded": True, "rows_inserted": len(rows)}
