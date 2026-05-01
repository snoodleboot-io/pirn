"""``WatermarkIncrementalExtract`` — SubTapestry that reads only rows
newer than the last successful run.

Composition:
1. :class:`ReadHighWaterMarkKnot` reads ``MAX(watermark_column)`` from
   the target table.
2. :class:`QueryNewRowsKnot` queries the source for rows whose watermark
   exceeds that value (or all rows on initial load).
3. :class:`DatabaseExecuteSink` writes the new rows to the target.

The high-water mark lives *in the target table* — pirn doesn't manage a
separate state store. This works when the target carries the watermark
column itself (a common pattern for append-only fact tables ordered by
``loaded_at`` / ``updated_at``).
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.data.specializations.ingestion.query_new_rows_knot import (
    QueryNewRowsKnot,
)
from pirn.domains.data.specializations.ingestion.read_high_water_mark_knot import (
    ReadHighWaterMarkKnot,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class WatermarkIncrementalExtract(SubTapestry):
    """Read source rows newer than the target's high-water mark."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_table: str,
        columns: Sequence[str],
        target_pool: DatabaseConnectionPool,
        target_table: str,
        watermark_column: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "WatermarkIncrementalExtract: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "WatermarkIncrementalExtract: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
            ("watermark_column", watermark_column),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"WatermarkIncrementalExtract: {label} must be a non-empty string"
                )
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("WatermarkIncrementalExtract: columns must be non-empty")
        self._source_pool = source_pool
        self._source_table = source_table
        self._columns = column_tuple
        self._target_pool = target_pool
        self._target_table = target_table
        self._watermark_column = watermark_column
        # Generate the insert query once; the columns drive both the SELECT and
        # the INSERT placeholder list, keeping them in lock-step.
        self._insert_query = self._build_insert_query()
        super().__init__(_config=_config, **kwargs)

    def _build_insert_query(self) -> str:
        column_list = ", ".join(self._columns)
        placeholders = ", ".join(["?"] * len(self._columns))
        return f"INSERT INTO {self._target_table} ({column_list}) VALUES ({placeholders})"

    async def process(self, **_: Any) -> RunResult:
        with Tapestry() as inner:
            high_water_mark = ReadHighWaterMarkKnot(
                pool=self._target_pool,
                table=self._target_table,
                watermark_column=self._watermark_column,
                _config=KnotConfig(id="high_water_mark"),
            )
            new_rows = QueryNewRowsKnot(
                pool=self._source_pool,
                table=self._source_table,
                columns=self._columns,
                watermark_column=self._watermark_column,
                high_water_mark=high_water_mark,
                _config=KnotConfig(id="extract"),
            )
            DatabaseExecuteSink(
                pool=self._target_pool,
                query=self._insert_query,
                rows=new_rows,
                _config=KnotConfig(id="load"),
            )
        return await self._run_inner(inner)
