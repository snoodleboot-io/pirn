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


class TestConstruction(unittest.TestCase):
    def test_rejects_non_expr_in_aggs(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "polars.Expr"):
                PolarsAggregate(
                    batch=batch, by=("a",), aggs=("sum(amount)",),  # type: ignore[arg-type]
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_empty_by(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                PolarsAggregate(
                    batch=batch, by=(),
                    aggs=(pl.col("x").sum(),),
                    _config=KnotConfig(id="a"),
                )
