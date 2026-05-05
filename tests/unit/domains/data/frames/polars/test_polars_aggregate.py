"""Tests for :class:`PolarsAggregate`."""

from __future__ import annotations

import unittest

import polars as pl
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_aggregate import PolarsAggregate
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_orders() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "region":   ["EU", "EU", "EU", "US", "US"],
                "amount":   [10.0, 25.0, 5.0,  100.0, None],
                "customer": ["alice", "bob", "alice", "carol", "carol"],
            }
        )
    )


def _orders_batch() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "region": ["EU", "EU", "US"],
                "amount": [10.0, 25.0, 100.0],
            }
        )
    )


class TestPolarsAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_sum_per_region(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PolarsAggregate(
                batch=batch,
                by=("region",),
                aggs=(pl.col("amount").sum().alias("total"),),
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["agg"]
        totals = dict(zip(out.frame["region"].to_list(), out.frame["total"].to_list()))
        assert totals["EU"] == 40.0
        assert totals["US"] == 100.0

    async def test_multiple_aggregations(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PolarsAggregate(
                batch=batch,
                by=("region",),
                aggs=(
                    pl.col("amount").sum().alias("total"),
                    pl.col("amount").mean().alias("avg"),
                    pl.col("customer").n_unique().alias("n_customers"),
                ),
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["agg"]
        eu = out.frame.filter(pl.col("region") == "EU").row(0, named=True)
        assert eu["total"] == 40.0
        assert eu["avg"] == pytest.approx(40.0 / 3)
        assert eu["n_customers"] == 2

    async def test_composite_group_by(self) -> None:
        @knot
        async def two_dim() -> PolarsDataBatch:
            return PolarsDataBatch(
                frame=pl.DataFrame(
                    {
                        "region": ["EU", "EU", "EU", "US"],
                        "tier":   ["A", "B", "A", "A"],
                        "amount": [1, 2, 3, 4],
                    }
                )
            )

        with Tapestry() as t:
            batch = two_dim(_config=KnotConfig(id="orders"))
            PolarsAggregate(
                batch=batch,
                by=("region", "tier"),
                aggs=(pl.col("amount").sum().alias("total"),),
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["agg"]
        assert out.row_count == 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        @knot
        async def emit_by() -> object:
            return ("region",)

        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            by_knot = emit_by(_config=KnotConfig(id="by"))
            PolarsAggregate(
                batch=batch,
                by=by_knot,
                aggs=(pl.col("amount").sum().alias("total"),),
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["agg"]
        assert "total" in out.frame.columns


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PolarsAggregate:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PolarsAggregate(
                batch=batch,
                by=("region",),
                aggs=(pl.col("amount").sum().alias("total"),),
                _config=KnotConfig(id="a"),
                **kwargs,
            )

    async def test_rejects_non_expr_in_aggs(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "polars.Expr"):
            await k.process(
                batch=_orders_batch(),
                by=("region",),
                aggs=("sum(amount)",),
            )

    async def test_rejects_empty_by(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_orders_batch(),
                by=(),
                aggs=(pl.col("amount").sum().alias("total"),),
            )

    async def test_rejects_empty_aggs(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_orders_batch(),
                by=("region",),
                aggs=(),
            )
