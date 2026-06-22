"""Tests for :class:`PolarsWindowCalc`."""

from __future__ import annotations

import unittest

try:
    import polars  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("polars not installed") from _e

import polars as pl
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn_data.frames.polars.polars_window_calc import PolarsWindowCalc


@knot
async def emit_orders() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "region": ["EU", "EU", "EU", "US", "US"],
                "amount": [10.0, 25.0, 5.0,  100.0, 50.0],
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


class TestPolarsWindowCalc(unittest.IsolatedAsyncioTestCase):
    async def test_partitioned_rank(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PolarsWindowCalc(
                batch=batch,
                windows=(
                    pl.col("amount")
                    .rank(method="ordinal", descending=True)
                    .over("region")
                    .alias("rank_in_region"),
                ),
                _config=KnotConfig(id="ranked"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["ranked"]
        assert "rank_in_region" in out.column_names
        # Largest EU amount (25.0) ranks 1; largest US amount (100.0) ranks 1.
        eu_rows = out.frame.filter(pl.col("region") == "EU").sort("amount")
        assert eu_rows["rank_in_region"].to_list() == [3, 2, 1]

    async def test_cumulative_sum(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PolarsWindowCalc(
                batch=batch,
                windows=(pl.col("amount").cum_sum().alias("running_total"),),
                _config=KnotConfig(id="cum"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["cum"]
        assert out.frame["running_total"].to_list() == [
            10.0, 35.0, 40.0, 140.0, 190.0,
        ]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_windows_from_upstream_knot(self) -> None:
        @knot
        async def emit_windows() -> object:
            return (pl.col("amount").cum_sum().alias("running_total"),)

        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            windows_knot = emit_windows(_config=KnotConfig(id="windows"))
            PolarsWindowCalc(
                batch=batch,
                windows=windows_knot,
                _config=KnotConfig(id="cum"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["cum"]
        assert "running_total" in out.column_names


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PolarsWindowCalc:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PolarsWindowCalc(
                batch=batch,
                windows=(pl.col("x").cum_sum().alias("y"),),
                _config=KnotConfig(id="w"),
                **kwargs,
            )

    async def test_rejects_empty_windows(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_orders_batch(),
                windows=(),
            )

    async def test_rejects_non_expr(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "polars.Expr"):
            await k.process(
                batch=_orders_batch(),
                windows=("rank()",),
            )
