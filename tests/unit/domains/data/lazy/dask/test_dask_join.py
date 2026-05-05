"""Tests for :class:`DaskJoin`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import dask.dataframe as dd
    import pandas as pd
except ImportError as _e:
    raise unittest.SkipTest("dask not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_join import DaskJoin
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _batch(data: dict) -> DaskDataFrame:
    return DaskDataFrame(frame=dd.from_pandas(pd.DataFrame(data), npartitions=1))


@knot
async def emit_left() -> DaskDataFrame:
    return _batch({"id": [1, 2], "val": ["a", "b"]})


@knot
async def emit_right() -> DaskDataFrame:
    return _batch({"id": [1, 3], "info": ["x", "z"]})


class TestDaskJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_column(self) -> None:
        with Tapestry() as t:
            left = emit_left(_config=KnotConfig(id="left"))
            right = emit_right(_config=KnotConfig(id="right"))
            DaskJoin(left=left, right=right, on="id", _config=KnotConfig(id="join"))
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["join"]
        df = out.frame.compute()
        assert len(df) == 1
        assert df["id"].iloc[0] == 1

    async def test_left_join_keeps_unmatched(self) -> None:
        with Tapestry() as t:
            left = emit_left(_config=KnotConfig(id="left"))
            right = emit_right(_config=KnotConfig(id="right"))
            DaskJoin(left=left, right=right, on="id", how="left", _config=KnotConfig(id="join"))
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["join"]
        df = out.frame.compute()
        assert len(df) == 2

    async def test_left_on_right_on(self) -> None:
        left_data = _batch({"a_id": [1, 2], "val": ["x", "y"]})
        right_data = _batch({"b_id": [1, 3], "info": ["p", "q"]})
        with Tapestry():
            class _Src(Source):
                async def process(self, **_: Any) -> DaskDataFrame:
                    return left_data

            class _Src2(Source):
                async def process(self, **_: Any) -> DaskDataFrame:
                    return right_data

            left_src = _Src(_config=KnotConfig(id="l"))
            right_src = _Src2(_config=KnotConfig(id="r"))
            j = DaskJoin(
                left=left_src, right=right_src,
                left_on="a_id", right_on="b_id",
                _config=KnotConfig(id="join"),
            )
        result = await j.process(
            left=left_data, right=right_data,
            on=None, left_on="a_id", right_on="b_id", how="inner",
        )
        df = result.frame.compute()
        assert len(df) == 1


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_how_from_upstream_knot(self) -> None:
        @knot
        async def emit_how() -> str:
            return "inner"

        with Tapestry() as t:
            left = emit_left(_config=KnotConfig(id="left"))
            right = emit_right(_config=KnotConfig(id="right"))
            how_knot = emit_how(_config=KnotConfig(id="how"))
            DaskJoin(
                left=left, right=right, on="id", how=how_knot,
                _config=KnotConfig(id="join"),
            )
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["join"]
        df = out.frame.compute()
        assert len(df) == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> DaskJoin:
        class _Src(Source):
            async def process(self, **_: Any) -> DaskDataFrame:
                return _batch({"id": [1, 2]})

        with Tapestry():
            left_src = _Src(_config=KnotConfig(id="l"))
            right_src = _Src(_config=KnotConfig(id="r"))
            return DaskJoin(left=left_src, right=right_src, _config=KnotConfig(id="join"), **kwargs)

    async def test_rejects_invalid_how(self) -> None:
        k = self._make_knot(on="id", how="full")
        with self.assertRaisesRegex(ValueError, "how must be one of"):
            await k.process(
                left=_batch({"id": [1]}),
                right=_batch({"id": [1]}),
                on="id",
                left_on=None,
                right_on=None,
                how="full",
            )

    async def test_rejects_cross_join_with_keys(self) -> None:
        k = self._make_knot(on="id", how="cross")
        with self.assertRaisesRegex(TypeError, "cross join takes no"):
            await k.process(
                left=_batch({"id": [1]}),
                right=_batch({"id": [1]}),
                on="id",
                left_on=None,
                right_on=None,
                how="cross",
            )

    async def test_rejects_non_cross_without_keys(self) -> None:
        k = self._make_knot(on="id")
        with self.assertRaisesRegex(TypeError, "must supply on"):
            await k.process(
                left=_batch({"id": [1]}),
                right=_batch({"id": [1]}),
                on=None,
                left_on=None,
                right_on=None,
                how="inner",
            )

    async def test_rejects_on_with_left_right_on(self) -> None:
        k = self._make_knot(on="id", left_on="id", right_on="id")
        with self.assertRaisesRegex(TypeError, "mutually exclusive"):
            await k.process(
                left=_batch({"id": [1]}),
                right=_batch({"id": [1]}),
                on="id",
                left_on="id",
                right_on="id",
                how="inner",
            )
