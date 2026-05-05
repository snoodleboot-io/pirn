"""Tests for :class:`DatafusionJoin`."""

from __future__ import annotations
import unittest

import datafusion as df

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn.domains.data.frames.datafusion.datafusion_join import DatafusionJoin
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> DatafusionDataBatch:
    ctx = df.SessionContext()
    frame = ctx.from_pylist(
        [
            {"user_id": 1, "name": "alice"},
            {"user_id": 2, "name": "bob"},
            {"user_id": 3, "name": "carol"},
        ]
    )
    return DatafusionDataBatch(frame=frame, context=ctx)


@knot
async def emit_orders() -> DatafusionDataBatch:
    ctx = df.SessionContext()
    frame = ctx.from_pylist(
        [
            {"user_id": 1, "amount": 10.0},
            {"user_id": 1, "amount": 20.0},
            {"user_id": 2, "amount": 30.0},
            {"user_id": 4, "amount": 40.0},
        ]
    )
    return DatafusionDataBatch(frame=frame, context=ctx)


class TestDatafusionJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_key(self) -> None:
        with Tapestry() as t:
            users = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            DatafusionJoin(
                left=users, right=orders, on="user_id", how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["joined"]
        rows = out.frame.to_pylist()
        # alice (2 orders) + bob (1) → 3 matched rows.
        assert len(rows) == 3

    async def test_left_join_keeps_unmatched_left_rows(self) -> None:
        with Tapestry() as t:
            users = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            DatafusionJoin(
                left=users, right=orders, on="user_id", how="left",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["joined"]
        rows = out.frame.to_pylist()
        names = {row["name"] for row in rows}
        # carol has no orders but appears in the left-join result.
        assert "carol" in names

    async def test_join_with_left_on_right_on(self) -> None:
        @knot
        async def emit_renamed_users() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.from_pylist(
                [{"uid": 1, "name": "alice"}, {"uid": 2, "name": "bob"}]
            )
            return DatafusionDataBatch(frame=frame, context=ctx)

        @knot
        async def emit_renamed_orders() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.from_pylist(
                [{"customer_id": 1, "amount": 10.0}, {"customer_id": 2, "amount": 20.0}]
            )
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry() as t:
            left = emit_renamed_users(_config=KnotConfig(id="users"))
            right = emit_renamed_orders(_config=KnotConfig(id="orders"))
            DatafusionJoin(
                left=left, right=right,
                left_on="uid", right_on="customer_id",
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["joined"]
        rows = out.frame.to_pylist()
        assert len(rows) == 2


class TestConstruction(unittest.TestCase):
    def test_rejects_unknown_how(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "how must be one of"):
                DatafusionJoin(
                    left=left, right=right, on="x", how="diagonal",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_both_on_and_left_on(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "not both"):
                DatafusionJoin(
                    left=left, right=right,
                    on="x", left_on="x", right_on="x",
                    _config=KnotConfig(id="j"),
                )

    def test_requires_either_on_or_both_left_right(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaises(TypeError):
                DatafusionJoin(
                    left=left, right=right, how="inner",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_unsafe_on_column(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "plain identifier"):
                DatafusionJoin(
                    left=left, right=right,
                    on="x; DROP TABLE t",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_mismatched_left_right_lengths(self) -> None:
        @knot
        async def empty() -> DatafusionDataBatch:
            ctx = df.SessionContext()
            frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
            return DatafusionDataBatch(frame=frame, context=ctx)

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "same length"):
                DatafusionJoin(
                    left=left, right=right,
                    left_on=("a", "b"), right_on=("c",),
                    _config=KnotConfig(id="j"),
                )
