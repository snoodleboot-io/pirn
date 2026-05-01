"""``GoldAggregation`` — aggregate a silver table into a gold business
mart.

Composition (Tier-1):
1. :class:`DatabaseQuerySource` reads silver rows.
2. :class:`TuplesToDataBatchKnot` keys them by column name.
3. :class:`Aggregate` groups by ``by`` and computes ``aggs``.
4. :class:`DataBatchToTuplesKnot` projects back to positional tuples.
5. :class:`DatabaseExecuteSink` writes to the gold table.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.domains.data.specializations.medallion.data_batch_to_tuples_knot import (
    DataBatchToTuplesKnot,
)
from pirn.domains.data.specializations.medallion.tuples_to_data_batch_knot import (
    TuplesToDataBatchKnot,
)
from pirn.domains.data.transforms.aggregate import Aggregate
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class GoldAggregation(SubTapestry):
    """Silver → Gold: group by + aggregations into a business mart."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        source_columns: Sequence[str],
        target_pool: DatabaseConnectionPool,
        target_table: str,
        by: Sequence[str],
        aggs: Mapping[str, AggregateSpec],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "GoldAggregation: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "GoldAggregation: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"GoldAggregation: {label} must be a non-empty string"
                )
        source_column_tuple = tuple(source_columns)
        if not source_column_tuple:
            raise ValueError("GoldAggregation: source_columns must be non-empty")
        by_tuple = tuple(by)
        if not by_tuple:
            raise ValueError("GoldAggregation: by must be non-empty")
        self._source_pool = source_pool
        self._source_query = source_query
        self._source_columns = source_column_tuple
        self._target_pool = target_pool
        self._target_table = target_table
        self._by = by_tuple
        self._aggs = dict(aggs)
        # Output columns: by + agg keys, in that order.
        self._target_columns = by_tuple + tuple(self._aggs.keys())
        self._insert_query = self._build_insert_query()
        super().__init__(_config=_config, **kwargs)

    def _build_insert_query(self) -> str:
        column_list = ", ".join(self._target_columns)
        placeholders = ", ".join(["?"] * len(self._target_columns))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        with Tapestry() as inner:
            extracted = DatabaseQuerySource(
                pool=self._source_pool,
                query=self._source_query,
                _config=KnotConfig(id="extract"),
            )
            as_batch = TuplesToDataBatchKnot(
                rows=extracted,
                column_names=self._source_columns,
                _config=KnotConfig(id="as_batch"),
            )
            aggregated = Aggregate(
                batch=as_batch,
                by=self._by,
                aggs=self._aggs,
                _config=KnotConfig(id="aggregate"),
            )
            tuples = DataBatchToTuplesKnot(
                batch=aggregated,
                column_names=self._target_columns,
                _config=KnotConfig(id="to_tuples"),
            )
            DatabaseExecuteSink(
                pool=self._target_pool,
                query=self._insert_query,
                rows=tuples,
                _config=KnotConfig(id="load"),
            )
        inner_result = await self._run_inner(inner)
        return {
            "succeeded": inner_result.succeeded,
            "target_table": self._target_table,
        }
