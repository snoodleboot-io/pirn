"""``AppendOnlyIngest`` — SubTapestry that inserts rows from a source query
into a target table without truncation, dedup, or watermarking.

Use this when:
- The source produces only new rows since the previous run (e.g. event
  log, audit trail, append-only fact table at the source).
- You manage idempotency via primary keys / unique constraints at the
  target rather than via watermark logic.

For source datasets that may re-emit older rows on each run, use
:class:`pirn.domains.data.specializations.ingestion.watermark_incremental_extract.WatermarkIncrementalExtract`
instead — this knot will happily insert duplicates if the source does.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class AppendOnlyIngest(SubTapestry):
    """Read all rows from a source query and append to a target table."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        insert_query: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("AppendOnlyIngest: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("AppendOnlyIngest: target_pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_query", source_query),
            ("insert_query", insert_query),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"AppendOnlyIngest: {label} must be a non-empty string")
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._insert_query = insert_query
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        with Tapestry() as inner:
            extracted = DatabaseQuerySource(
                pool=self._source_pool,
                query=self._source_query,
                _config=KnotConfig(id="extract"),
            )
            DatabaseExecuteSink(
                pool=self._target_pool,
                query=self._insert_query,
                rows=extracted,
                _config=KnotConfig(id="load"),
            )
        return await self._run_inner(inner)
