"""Tests for :class:`DatafusionFilter`."""

from __future__ import annotations

import unittest

import datafusion as df

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn.domains.data.frames.datafusion.datafusion_filter import (
    DatafusionFilter,
)
from pirn.tapestry import Tapestry


def _make_batch() -> DatafusionDataBatch:
    ctx = df.SessionContext()
    frame = ctx.from_pylist(
        [
            {"id": 1, "active": True,  "region": "EU"},
            {"id": 2, "active": False, "region": "US"},
            {"id": 3, "active": True,  "region": "US"},
            {"id": 4, "active": False, "region": "EU"},
        ]
    )
    return DatafusionDataBatch(frame=frame, context=ctx)


@knot
async def emit_users() -> DatafusionDataBatch:
    return _make_batch()


class TestDatafusionFilter(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_rows_matching_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DatafusionFilter(
                batch=batch,
                predicate="active",
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["active"]
        ids = sorted(row["id"] for row in out.frame.to_pylist())
        assert ids == [1, 3]

    async def test_compound_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DatafusionFilter(
                batch=batch,
                predicate="region = 'EU' AND active",
                _config=KnotConfig(id="active_eu"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["active_eu"]
        ids = sorted(row["id"] for row in out.frame.to_pylist())
        assert ids == [1]

    async def test_expression_callable(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DatafusionFilter(
                batch=batch,
                expression=lambda frame: df.col("active"),
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["active"]
        ids = sorted(row["id"] for row in out.frame.to_pylist())
        assert ids == [1, 3]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        @knot
        async def emit_predicate() -> str:
            return "active"

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            pred_knot = emit_predicate(_config=KnotConfig(id="pred"))
            DatafusionFilter(
                batch=batch,
                predicate=pred_knot,
                _config=KnotConfig(id="filtered"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["filtered"]
        ids = sorted(row["id"] for row in out.frame.to_pylist())
        assert ids == [1, 3]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: object) -> DatafusionFilter:
        @knot
        async def upstream() -> DatafusionDataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return DatafusionFilter(batch=batch, _config=KnotConfig(id="f"), **kwargs)

    async def test_rejects_neither_predicate_nor_expression(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "provide either"):
            await k.process(batch=_make_batch(), predicate=None, expression=None)

    async def test_rejects_empty_predicate(self) -> None:
        k = await self._make_knot(predicate="   ")
        with self.assertRaisesRegex(ValueError, "empty"):
            await k.process(batch=_make_batch(), predicate="   ", expression=None)

    async def test_rejects_obvious_injection(self) -> None:
        k = await self._make_knot(predicate="1 = 1; DROP TABLE users")
        with self.assertRaisesRegex(ValueError, "forbidden"):
            await k.process(
                batch=_make_batch(),
                predicate="1 = 1; DROP TABLE users",
                expression=None,
            )

    async def test_rejects_both_predicate_and_expression(self) -> None:
        k = await self._make_knot(predicate="x", expression=lambda f: df.col("x"))
        with self.assertRaisesRegex(TypeError, "not both"):
            await k.process(
                batch=_make_batch(),
                predicate="x",
                expression=lambda f: df.col("x"),
            )
