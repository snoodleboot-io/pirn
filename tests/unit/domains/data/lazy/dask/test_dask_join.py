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
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_join import DaskJoin
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _batch(data: dict) -> DaskDataFrame:
    return DaskDataFrame(frame=dd.from_pandas(pd.DataFrame(data), npartitions=1))


class _DaskSource(Source):
    async def process(self, **_: Any) -> DaskDataFrame:
        return _batch({"id": [1, 2]})


class TestDaskJoinConstruction(unittest.TestCase):
    def test_valid_on_join(self) -> None:
        with Tapestry():
            left = _DaskSource(_config=KnotConfig(id="left"))
            right = _DaskSource(_config=KnotConfig(id="right"))
            j = DaskJoin(left=left, right=right, on="id", _config=KnotConfig(id="join"))
        self.assertEqual(j.how, "inner")

    def test_rejects_invalid_how(self) -> None:
        with Tapestry():
            left = _DaskSource(_config=KnotConfig(id="left"))
            right = _DaskSource(_config=KnotConfig(id="right"))
            with self.assertRaises(ValueError):
                DaskJoin(left=left, right=right, on="id", how="full", _config=KnotConfig(id="join"))

    def test_cross_join_no_keys(self) -> None:
        with Tapestry():
            left = _DaskSource(_config=KnotConfig(id="left"))
            right = _DaskSource(_config=KnotConfig(id="right"))
            j = DaskJoin(left=left, right=right, how="cross", _config=KnotConfig(id="join"))
        self.assertEqual(j.how, "cross")

    def test_non_cross_requires_on_or_left_right(self) -> None:
        with Tapestry():
            left = _DaskSource(_config=KnotConfig(id="left"))
            right = _DaskSource(_config=KnotConfig(id="right"))
            with self.assertRaises(TypeError):
                DaskJoin(left=left, right=right, _config=KnotConfig(id="join"))

    def test_on_mutually_exclusive_with_left_right(self) -> None:
        with Tapestry():
            left = _DaskSource(_config=KnotConfig(id="left"))
            right = _DaskSource(_config=KnotConfig(id="right"))
            with self.assertRaises(TypeError):
                DaskJoin(
                    left=left, right=right, on="id", left_on="id", right_on="id",
                    _config=KnotConfig(id="join"),
                )


class TestDaskJoinProcess(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join(self) -> None:
        left_data = _batch({"id": [1, 2], "val": ["a", "b"]})
        right_data = _batch({"id": [1, 3], "info": ["x", "z"]})
        with Tapestry():
            left = _DaskSource(_config=KnotConfig(id="left"))
            right = _DaskSource(_config=KnotConfig(id="right"))
            j = DaskJoin(left=left, right=right, on="id", _config=KnotConfig(id="join"))
        result = await j.process(left=left_data, right=right_data)
        df = result.frame.compute()
        self.assertEqual(len(df), 1)
        self.assertEqual(df["id"].iloc[0], 1)
