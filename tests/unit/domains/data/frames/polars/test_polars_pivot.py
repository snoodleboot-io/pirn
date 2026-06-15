"""Tests for :class:`PolarsPivot`."""

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
from pirn_data.frames.polars.polars_pivot import PolarsPivot


@knot
async def emit_long() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "user":   ["alice", "alice", "bob",   "bob"],
                "metric": ["clicks", "views", "clicks", "views"],
                "value":  [3,         100,    7,        200],
            }
        )
    )


def _long_batch() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "user":   ["alice", "alice"],
                "metric": ["clicks", "views"],
                "value":  [3, 100],
            }
        )
    )


class TestPolarsPivot(unittest.IsolatedAsyncioTestCase):
    async def test_wide_reshape(self) -> None:
        with Tapestry() as t:
            batch = emit_long(_config=KnotConfig(id="long"))
            PolarsPivot(
                batch=batch,
                on="metric",
                index="user",
                values="value",
                _config=KnotConfig(id="wide"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["wide"]
        assert set(out.column_names) == {"user", "clicks", "views"}
        alice = out.frame.filter(pl.col("user") == "alice").row(0, named=True)
        assert alice["clicks"] == 3
        assert alice["views"] == 100

    async def test_aggregate_function_sum(self) -> None:
        @knot
        async def with_dups() -> PolarsDataBatch:
            return PolarsDataBatch(
                frame=pl.DataFrame(
                    {
                        "user":   ["alice", "alice", "alice"],
                        "metric": ["clicks", "clicks", "views"],
                        "value":  [1, 2, 5],
                    }
                )
            )

        with Tapestry() as t:
            batch = with_dups(_config=KnotConfig(id="dup"))
            PolarsPivot(
                batch=batch,
                on="metric",
                index="user",
                values="value",
                aggregate_function="sum",
                _config=KnotConfig(id="wide"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["wide"]
        alice = out.frame.row(0, named=True)
        assert alice["clicks"] == 3   # 1 + 2
        assert alice["views"] == 5


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_aggregate_function_from_upstream_knot(self) -> None:
        @knot
        async def emit_agg_fn() -> object:
            return "first"

        with Tapestry() as t:
            batch = emit_long(_config=KnotConfig(id="long"))
            agg_knot = emit_agg_fn(_config=KnotConfig(id="agg_fn"))
            PolarsPivot(
                batch=batch,
                on="metric",
                index="user",
                values="value",
                aggregate_function=agg_knot,
                _config=KnotConfig(id="wide"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["wide"]
        assert set(out.column_names) == {"user", "clicks", "views"}


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PolarsPivot:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PolarsPivot(
                batch=batch,
                on="metric",
                index="user",
                values="value",
                _config=KnotConfig(id="p"),
                **kwargs,
            )

    async def test_rejects_unknown_aggregate(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "aggregate_function"):
            await k.process(
                batch=_long_batch(),
                on="metric",
                index="user",
                values="value",
                aggregate_function="median",
            )

    async def test_rejects_empty_string_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_long_batch(),
                on="",
                index="user",
                values="value",
                aggregate_function="first",
            )
