"""Tests for :class:`PandasJoin`."""

from __future__ import annotations
import unittest

import pandas as pd

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.frames.pandas.pandas_join import PandasJoin
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]}
        )
    )


@knot
async def emit_orders() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]}
        )
    )


class TestPandasJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_key(self) -> None:
        with Tapestry() as t:
            users  = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            PandasJoin(
                left=users, right=orders, on="user_id", how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["joined"]
        # Only user_ids 1 and 2 appear on both sides; alice has 2 orders, bob has 1.
        assert out.row_count == 3
        assert set(out.frame["name"].tolist()) == {"alice", "bob"}

    async def test_left_join_keeps_unmatched_left_rows(self) -> None:
        with Tapestry() as t:
            users  = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            PandasJoin(
                left=users, right=orders, on="user_id", how="left",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["joined"]
        # All 3 users appear; carol has no orders → null amount; alice has 2 rows.
        names = out.frame["name"].tolist()
        assert "carol" in names

    async def test_left_on_right_on_with_different_names(self) -> None:
        @knot
        async def emit_orders_renamed() -> PandasDataBatch:
            return PandasDataBatch(
                frame=pd.DataFrame(
                    {"customer_id": [1, 2], "amount": [10.0, 20.0]}
                )
            )

        with Tapestry() as t:
            users  = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders_renamed(_config=KnotConfig(id="orders"))
            PandasJoin(
                left=users, right=orders,
                left_on="user_id", right_on="customer_id",
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["joined"]
        assert out.row_count == 2

    async def test_cross_join(self) -> None:
        @knot
        async def emit_left() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame({"x": [1, 2]}))

        @knot
        async def emit_right() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame({"y": ["a", "b", "c"]}))

        with Tapestry() as t:
            left = emit_left(_config=KnotConfig(id="left"))
            right = emit_right(_config=KnotConfig(id="right"))
            PandasJoin(
                left=left, right=right, how="cross",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["joined"]
        assert out.row_count == 6   # 2 × 3


class TestConstruction(unittest.TestCase):
    def test_rejects_unknown_how(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "how must be one of"):
                PandasJoin(
                    left=left, right=right, on="x", how="diagonal",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_semi_and_anti_joins(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "does not natively support"):
                PandasJoin(
                    left=left, right=right, on="x", how="semi",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_both_on_and_left_on(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "not both"):
                PandasJoin(
                    left=left, right=right,
                    on="x", left_on="x", right_on="x",
                    _config=KnotConfig(id="j"),
                )

    def test_requires_keys_for_non_cross_join(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "provide on="):
                PandasJoin(
                    left=left, right=right, how="inner",
                    _config=KnotConfig(id="j"),
                )

    def test_cross_join_rejects_keys(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "cross join takes no"):
                PandasJoin(
                    left=left, right=right, how="cross", on="x",
                    _config=KnotConfig(id="j"),
                )
