"""Tests for :class:`PandasJoin`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e

import pandas as pd
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn_data.frames.pandas.pandas_join import PandasJoin


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


def _empty_batch() -> PandasDataBatch:
    return PandasDataBatch(frame=pd.DataFrame({"x": [1]}))


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
        assert out.row_count == 6   # 2 x 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_how_from_upstream_knot(self) -> None:
        @knot
        async def emit_how() -> object:
            return "inner"

        with Tapestry() as t:
            users  = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            how_knot = emit_how(_config=KnotConfig(id="how"))
            PandasJoin(
                left=users, right=orders, on="user_id", how=how_knot,
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["joined"]
        assert out.row_count == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PandasJoin:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame({"x": [1]}))

        with Tapestry():
            left  = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            return PandasJoin(
                left=left, right=right, on="x",
                _config=KnotConfig(id="j"),
                **kwargs,
            )

    async def test_rejects_unknown_how(self) -> None:
        k = self._make_knot()
        left = _empty_batch()
        right = _empty_batch()
        with self.assertRaisesRegex(ValueError, "how must be one of"):
            await k.process(
                left=left, right=right, on="x", left_on=None,
                right_on=None, how="diagonal", suffix="_right",
            )

    async def test_rejects_semi_join(self) -> None:
        k = self._make_knot()
        left = _empty_batch()
        right = _empty_batch()
        with self.assertRaisesRegex(ValueError, "does not natively support"):
            await k.process(
                left=left, right=right, on="x", left_on=None,
                right_on=None, how="semi", suffix="_right",
            )

    async def test_rejects_both_on_and_left_on(self) -> None:
        k = self._make_knot()
        left = _empty_batch()
        right = _empty_batch()
        with self.assertRaisesRegex(TypeError, "not both"):
            await k.process(
                left=left, right=right, on="x", left_on="x",
                right_on="x", how="inner", suffix="_right",
            )

    async def test_requires_keys_for_non_cross_join(self) -> None:
        k = self._make_knot()
        left = _empty_batch()
        right = _empty_batch()
        with self.assertRaisesRegex(TypeError, "provide on="):
            await k.process(
                left=left, right=right, on=None, left_on=None,
                right_on=None, how="inner", suffix="_right",
            )

    async def test_cross_join_rejects_keys(self) -> None:
        k = self._make_knot()
        left = _empty_batch()
        right = _empty_batch()
        with self.assertRaisesRegex(TypeError, "cross join takes no"):
            await k.process(
                left=left, right=right, on="x", left_on=None,
                right_on=None, how="cross", suffix="_right",
            )
