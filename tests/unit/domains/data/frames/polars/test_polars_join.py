"""Tests for :class:`PolarsJoin`."""

from __future__ import annotations
import unittest

import polars as pl

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.frames.polars.polars_join import PolarsJoin
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]}
        )
    )


@knot
async def emit_orders() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]}
        )
    )


class TestPolarsJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_key(self) -> None:
        with Tapestry() as t:
            users  = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            PolarsJoin(
                left=users, right=orders, on="user_id", how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["joined"]
        # Only user_ids 1 and 2 appear on both sides; alice has 2 orders, bob has 1.
        assert out.row_count == 3
        assert set(out.frame["name"].to_list()) == {"alice", "bob"}

    async def test_left_join_keeps_unmatched_left_rows(self) -> None:
        with Tapestry() as t:
            users  = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            PolarsJoin(
                left=users, right=orders, on="user_id", how="left",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["joined"]
        # All 3 users appear; carol has no orders → null amount; alice has 2 rows.
        names = out.frame["name"].to_list()
        assert "carol" in names

    async def test_left_on_right_on_with_different_names(self) -> None:
        @knot
        async def emit_orders_renamed() -> PolarsDataBatch:
            return PolarsDataBatch(
                frame=pl.DataFrame(
                    {"customer_id": [1, 2], "amount": [10.0, 20.0]}
                )
            )

        with Tapestry() as t:
            users  = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders_renamed(_config=KnotConfig(id="orders"))
            PolarsJoin(
                left=users, right=orders,
                left_on="user_id", right_on="customer_id",
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["joined"]
        assert out.row_count == 2

    async def test_cross_join(self) -> None:
        @knot
        async def emit_left() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame({"x": [1, 2]}))

        @knot
        async def emit_right() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame({"y": ["a", "b", "c"]}))

        with Tapestry() as t:
            left = emit_left(_config=KnotConfig(id="left"))
            right = emit_right(_config=KnotConfig(id="right"))
            PolarsJoin(
                left=left, right=right, how="cross",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["joined"]
        assert out.row_count == 6   # 2 × 3


class TestConstruction(unittest.TestCase):
    def test_rejects_unknown_how(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "how must be one of"):
                PolarsJoin(
                    left=left, right=right, on="x", how="diagonal",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_both_on_and_left_on(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "not both"):
                PolarsJoin(
                    left=left, right=right,
                    on="x", left_on="x", right_on="x",
                    _config=KnotConfig(id="j"),
                )

    def test_requires_keys_for_non_cross_join(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "provide on="):
                PolarsJoin(
                    left=left, right=right, how="inner",
                    _config=KnotConfig(id="j"),
                )

    def test_cross_join_rejects_keys(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "cross join takes no"):
                PolarsJoin(
                    left=left, right=right, how="cross", on="x",
                    _config=KnotConfig(id="j"),
                )
