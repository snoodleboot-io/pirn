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


def _make_empty_batch() -> DatafusionDataBatch:
    ctx = df.SessionContext()
    frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
    return DatafusionDataBatch(frame=frame, context=ctx)


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


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        @knot
        async def emit_by() -> tuple:
            return ("region",)

        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            by_knot = emit_by(_config=KnotConfig(id="by"))
            DatafusionAggregate(
                batch=batch,
                by=by_knot,
                aggs={"total": dff.sum(df.col("amount"))},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["agg"]
        rows = {row["region"]: row["total"] for row in out.frame.to_pylist()}
        assert rows["EU"] == 40.0
        assert rows["US"] == 100.0


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> DatafusionAggregate:
        @knot
        async def empty() -> DatafusionDataBatch:
            return _make_empty_batch()

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return DatafusionAggregate(
                batch=batch, _config=KnotConfig(id="a"), **kwargs
            )

    async def test_rejects_empty_by(self) -> None:
        k = self._make_knot(by=(), aggs={"total": dff.sum(df.col("x"))})
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_make_empty_batch(),
                by=(),
                aggs={"total": dff.sum(df.col("x"))},
            )

    async def test_rejects_unsafe_output_name(self) -> None:
        k = self._make_knot(by=("a",), aggs={"bad name!": dff.sum(df.col("x"))})
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await k.process(
                batch=_make_empty_batch(),
                by=("a",),
                aggs={"bad name!": dff.sum(df.col("x"))},
            )

    async def test_rejects_non_expression_value(self) -> None:
        k = self._make_knot(by=("a",), aggs={"total": "SUM(x)"})  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "datafusion.Expr"):
            await k.process(
                batch=_make_empty_batch(),
                by=("a",),
                aggs={"total": "SUM(x)"},  # type: ignore[arg-type]
            )
