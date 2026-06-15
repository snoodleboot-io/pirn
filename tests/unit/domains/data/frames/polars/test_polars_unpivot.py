"""Tests for :class:`PolarsUnpivot`."""

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
from pirn_data.frames.polars.polars_unpivot import PolarsUnpivot


@knot
async def emit_wide() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "user":   ["alice", "bob"],
                "clicks": [3, 7],
                "views":  [100, 200],
            }
        )
    )


def _wide_batch() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "user":   ["alice", "bob"],
                "clicks": [3, 7],
                "views":  [100, 200],
            }
        )
    )


class TestPolarsUnpivot(unittest.IsolatedAsyncioTestCase):
    async def test_long_reshape(self) -> None:
        with Tapestry() as t:
            batch = emit_wide(_config=KnotConfig(id="wide"))
            PolarsUnpivot(
                batch=batch,
                on=("clicks", "views"),
                index=("user",),
                variable_name="metric",
                value_name="value",
                _config=KnotConfig(id="long"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["long"]
        assert out.row_count == 4   # 2 users x 2 metrics
        assert set(out.column_names) == {"user", "metric", "value"}

    async def test_default_variable_and_value_names(self) -> None:
        with Tapestry() as t:
            batch = emit_wide(_config=KnotConfig(id="wide"))
            PolarsUnpivot(
                batch=batch,
                on=("clicks", "views"),
                index=("user",),
                _config=KnotConfig(id="long"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["long"]
        assert "variable" in out.column_names
        assert "value" in out.column_names


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_on_from_upstream_knot(self) -> None:
        @knot
        async def emit_on() -> object:
            return ("clicks", "views")

        with Tapestry() as t:
            batch = emit_wide(_config=KnotConfig(id="wide"))
            on_knot = emit_on(_config=KnotConfig(id="on"))
            PolarsUnpivot(
                batch=batch,
                on=on_knot,
                index=("user",),
                _config=KnotConfig(id="long"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["long"]
        assert out.row_count == 4


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PolarsUnpivot:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PolarsUnpivot(
                batch=batch,
                on=("clicks",),
                _config=KnotConfig(id="u"),
                **kwargs,
            )

    async def test_rejects_empty_on(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_wide_batch(),
                on=(),
                index=None,
                variable_name="variable",
                value_name="value",
            )

    async def test_rejects_empty_variable_name(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "variable_name"):
            await k.process(
                batch=_wide_batch(),
                on=("clicks",),
                index=None,
                variable_name="",
                value_name="value",
            )

    async def test_rejects_empty_value_name(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "value_name"):
            await k.process(
                batch=_wide_batch(),
                on=("clicks",),
                index=None,
                variable_name="variable",
                value_name="",
            )
