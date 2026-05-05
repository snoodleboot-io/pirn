"""Tests for :class:`PolarsPivot`."""

from __future__ import annotations
import unittest

import polars as pl

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.frames.polars.polars_pivot import PolarsPivot
from pirn.tapestry import Tapestry


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


class TestConstruction(unittest.TestCase):
    def test_rejects_unknown_aggregate(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "aggregate_function"):
                PolarsPivot(
                    batch=batch, on="x", index="y", values="z",
                    aggregate_function="median",
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_empty_string_column(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                PolarsPivot(
                    batch=batch, on="", index="y", values="z",
                    _config=KnotConfig(id="p"),
                )
