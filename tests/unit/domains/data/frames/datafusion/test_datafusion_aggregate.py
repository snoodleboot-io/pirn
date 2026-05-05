"""Tests for :class:`DatafusionAggregate`."""

from __future__ import annotations
import unittest

import datafusion as df
import datafusion.functions as dff

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.datafusion.datafusion_aggregate import (
    DatafusionAggregate,
)
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn.tapestry import Tapestry


@knot
async def emit_orders() -> DatafusionDataBatch:
    ctx = df.SessionContext()
    frame = ctx.from_pylist(
        [
            {"region": "EU", "amount": 10.0, "customer": "alice"},
            {"region": "EU", "amount": 25.0, "customer": "bob"},
            {"region": "EU", "amount": 5.0,  "customer": "alice"},
            {"region": "US", "amount": 100.0, "customer": "carol"},
        ]
    )
    return DatafusionDataBatch(frame=frame, context=ctx)


class TestDatafusionAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_sum_per_region(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            DatafusionAggregate(
                batch=batch,
                by=("region",),
                aggs={"total": dff.sum(df.col("amount"))},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["agg"]
        rows = out.frame.to_pylist()
        totals = {row["region"]: row["total"] for row in rows}
        assert totals["EU"] == 40.0
        assert totals["US"] == 100.0

    async def test_callable_aggregation(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            DatafusionAggregate(
                batch=batch,
                by=("region",),
                aggs={
                    "n_customers": lambda frame: dff.count(df.col("customer")),
                },
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["agg"]
        rows = out.frame.to_pylist()
        counts = {row["region"]: row["n_customers"] for row in rows}
        assert counts["EU"] == 3
        assert counts["US"] == 1


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_by(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                DatafusionAggregate(
                    batch=batch, by=(),
                    aggs={"total": dff.sum(df.col("x"))},
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_unsafe_output_name(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "plain identifier"):
                DatafusionAggregate(
                    batch=batch, by=("a",),
                    aggs={"bad name!": dff.sum(df.col("x"))},
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_non_expression_value(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "datafusion.Expr"):
                DatafusionAggregate(
                    batch=batch, by=("a",),
                    aggs={"total": "SUM(x)"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="a"),
                )
