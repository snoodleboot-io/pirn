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


@knot
async def emit_users() -> DatafusionDataBatch:
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


class TestConstruction(unittest.TestCase):
    def test_rejects_neither_predicate_nor_expression(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "provide either"):
                DatafusionFilter(
                    batch=batch,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_empty_predicate(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "empty"):
                DatafusionFilter(
                    batch=batch, predicate="   ",
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_obvious_injection(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "forbidden"):
                DatafusionFilter(
                    batch=batch,
                    predicate="1 = 1; DROP TABLE users",
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_both_predicate_and_expression(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "not both"):
                DatafusionFilter(
                    batch=batch,
                    predicate="x",
                    expression=lambda f: df.col("x"),
                    _config=KnotConfig(id="f"),
                )
