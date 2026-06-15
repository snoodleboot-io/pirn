"""Tests for :class:`PolarsFilter`."""

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
from pirn_data.frames.polars.polars_filter import PolarsFilter


@knot
async def emit_users() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "id":     [1, 2, 3, 4],
                "active": [True, False, True, False],
                "region": ["EU", "US", "US", "EU"],
            }
        )
    )


def _users_batch() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "id":     [1, 2, 3, 4],
                "active": [True, False, True, False],
                "region": ["EU", "US", "US", "EU"],
            }
        )
    )


class TestPolarsFilter(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_rows_matching_expression(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PolarsFilter(
                batch=batch,
                expression=pl.col("active"),
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["active"]
        assert tuple(out.frame["id"].to_list()) == (1, 3)

    async def test_compound_expression(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PolarsFilter(
                batch=batch,
                expression=(pl.col("region") == "EU") & (pl.col("active")),
                _config=KnotConfig(id="active_eu"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["active_eu"]
        assert tuple(out.frame["id"].to_list()) == (1,)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_expression_from_upstream_knot(self) -> None:
        @knot
        async def emit_expression() -> object:
            return pl.col("active")

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            expr_knot = emit_expression(_config=KnotConfig(id="expr"))
            PolarsFilter(
                batch=batch,
                expression=expr_knot,
                _config=KnotConfig(id="filtered"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["filtered"]
        assert tuple(out.frame["id"].to_list()) == (1, 3)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PolarsFilter:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PolarsFilter(
                batch=batch,
                expression=pl.col("active"),
                _config=KnotConfig(id="f"),
                **kwargs,
            )

    async def test_rejects_python_callable(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "polars.Expr"):
            await k.process(
                batch=_users_batch(),
                expression=lambda r: True,
            )

    async def test_rejects_string_expression(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "polars.Expr"):
            await k.process(
                batch=_users_batch(),
                expression="active == True",
            )
