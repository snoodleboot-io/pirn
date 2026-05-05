"""``FullRefreshExtract`` — SubTapestry that drops + reloads a target table
from a source query on every run.

Composition: read all rows from ``source_pool`` via ``source_query``,
delete every row from ``target_table`` on ``target_pool``, then insert
the fetched rows via ``insert_query``. No state, no watermark — every
run is a complete refresh.

Use this when:
- The source dataset is small enough to read in full each run.
- You need *exact* parity with the source after every run (no drift
  from incremental gaps).
- You don't have a reliable watermark column.

Pools are held as SubTapestry instance state and passed directly to the
inner knots' constructors. They never flow through pirn's
content-addressing serialiser thanks to the pool interface's
``__get_pydantic_core_schema__`` opaque-type schema with a stable
identity-based serialiser.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.domains.data.specializations.ingestion.rows_behind_truncate_check_knot import (
    RowsBehindTruncateCheckKnot,
)
from pirn.domains.data.specializations.ingestion.truncate_table_knot import (
    TruncateTableKnot,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class FullRefreshExtract(SubTapestry):
    """Drop + reload a target table from a source query."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        insert_query: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "FullRefreshExtract: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "FullRefreshExtract: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
            ("insert_query", insert_query),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"FullRefreshExtract: {label} must be a non-empty string"
                )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._insert_query = insert_query
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> RunResult:
        """Truncate the target table, extract all source rows, and reload them, returning a RunResult.

        Returns:
            A RunResult summarising the outcome of the inner tapestry execution.
        """
        with Tapestry() as inner:
            extracted = DatabaseQuerySource(
                pool=self._source_pool,
                query=self._source_query,
                _config=KnotConfig(id="extract"),
            )
            truncated = TruncateTableKnot(
                pool=self._target_pool,
                table=self._target_table,
                _config=KnotConfig(id="truncate"),
            )
            gated = RowsBehindTruncateCheckKnot(
                rows=extracted,
                gate=truncated,
                _config=KnotConfig(id="gated"),
            )
            DatabaseExecuteSink(
                pool=self._target_pool,
                query=self._insert_query,
                rows=gated,
                _config=KnotConfig(id="load"),
            )
        return await self._run_inner(inner)
