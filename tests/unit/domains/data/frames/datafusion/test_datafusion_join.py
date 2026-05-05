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


def _make_empty_batch() -> DatafusionDataBatch:
    ctx = df.SessionContext()
    frame = ctx.sql("SELECT NULL AS x WHERE FALSE")
    return DatafusionDataBatch(frame=frame, context=ctx)


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


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> DatafusionJoin:
        @knot
        async def empty() -> DatafusionDataBatch:
            return _make_empty_batch()

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            return DatafusionJoin(left=left, right=right, _config=KnotConfig(id="j"), **kwargs)

    async def test_rejects_unknown_how(self) -> None:
        k = self._make_knot(on="x", how="diagonal")
        with self.assertRaisesRegex(ValueError, "how must be one of"):
            await k.process(
                left=_make_empty_batch(), right=_make_empty_batch(),
                on="x", left_on=None, right_on=None, how="diagonal",
            )

    async def test_rejects_both_on_and_left_on(self) -> None:
        k = self._make_knot(on="x", left_on="x", right_on="x")
        with self.assertRaisesRegex(TypeError, "not both"):
            await k.process(
                left=_make_empty_batch(), right=_make_empty_batch(),
                on="x", left_on="x", right_on="x", how="inner",
            )

    async def test_requires_either_on_or_both_left_right(self) -> None:
        k = self._make_knot(how="inner")
        with self.assertRaises(TypeError):
            await k.process(
                left=_make_empty_batch(), right=_make_empty_batch(),
                on=None, left_on=None, right_on=None, how="inner",
            )

    async def test_rejects_unsafe_on_column(self) -> None:
        k = self._make_knot(on="x; DROP TABLE t")
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await k.process(
                left=_make_empty_batch(), right=_make_empty_batch(),
                on="x; DROP TABLE t", left_on=None, right_on=None, how="inner",
            )

    async def test_rejects_mismatched_left_right_lengths(self) -> None:
        k = self._make_knot(left_on=("a", "b"), right_on=("c",))
        with self.assertRaisesRegex(ValueError, "same length"):
            await k.process(
                left=_make_empty_batch(), right=_make_empty_batch(),
                on=None, left_on=("a", "b"), right_on=("c",), how="inner",
            )
