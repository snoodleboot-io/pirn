"""Tests for :class:`SparkJoin`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_data.lazy.spark.spark_dataframe import SparkDataFrame

try:
    import pyspark.sql  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyspark not installed") from _e

from pirn.nodes.source import Source
from pirn.tapestry import Tapestry
from pirn_data.lazy.spark.spark_join import SparkJoin


def _mock_sdf(cols: list[str] | None = None) -> SparkDataFrame:
    frame = MagicMock()
    frame.columns = cols or ["id", "val"]
    joined = MagicMock()
    frame.join.return_value = joined
    frame.crossJoin.return_value = joined
    # Support column-expression comparisons for left_on/right_on mode
    frame.__getitem__ = lambda self, key: MagicMock()
    return SparkDataFrame(frame=frame)


class _SparkLeft(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf(["id", "a"])


class _SparkRight(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf(["id", "b"])


class TestSparkJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_key(self) -> None:
        left = _mock_sdf(["id", "a"])
        right = _mock_sdf(["id", "b"])
        with Tapestry():
            lsrc = _SparkLeft(_config=KnotConfig(id="left"))
            rsrc = _SparkRight(_config=KnotConfig(id="right"))
            j = SparkJoin(left=lsrc, right=rsrc, on="id", _config=KnotConfig(id="join"))
        result = await j.process(
            left=left,
            right=right,
            on="id",
            left_on=None,
            right_on=None,
            how="inner",
        )
        self.assertIsInstance(result, SparkDataFrame)
        left.frame.join.assert_called_once_with(right.frame, on="id", how="inner")

    async def test_cross_join(self) -> None:
        left = _mock_sdf(["a"])
        right = _mock_sdf(["b"])
        with Tapestry():
            lsrc = _SparkLeft(_config=KnotConfig(id="left"))
            rsrc = _SparkRight(_config=KnotConfig(id="right"))
            j = SparkJoin(left=lsrc, right=rsrc, how="cross", _config=KnotConfig(id="join"))
        result = await j.process(
            left=left,
            right=right,
            on=None,
            left_on=None,
            right_on=None,
            how="cross",
        )
        self.assertIsInstance(result, SparkDataFrame)
        left.frame.crossJoin.assert_called_once_with(right.frame)

    async def test_left_join_with_list_on(self) -> None:
        left = _mock_sdf(["id", "a"])
        right = _mock_sdf(["id", "b"])
        with Tapestry():
            lsrc = _SparkLeft(_config=KnotConfig(id="left"))
            rsrc = _SparkRight(_config=KnotConfig(id="right"))
            j = SparkJoin(
                left=lsrc, right=rsrc, on=["id"], how="left", _config=KnotConfig(id="join")
            )
        result = await j.process(
            left=left,
            right=right,
            on=["id"],
            left_on=None,
            right_on=None,
            how="left",
        )
        self.assertIsInstance(result, SparkDataFrame)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_how_from_upstream_knot(self) -> None:
        @knot
        async def emit_how() -> str:
            return "inner"

        with Tapestry():
            lsrc = _SparkLeft(_config=KnotConfig(id="left"))
            rsrc = _SparkRight(_config=KnotConfig(id="right"))
            how_knot = emit_how(_config=KnotConfig(id="how"))
            SparkJoin(
                left=lsrc, right=rsrc, on="id", how=how_knot, _config=KnotConfig(id="join")
            )
        # Construction with Knot input succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> SparkJoin:
        with Tapestry():
            lsrc = _SparkLeft(_config=KnotConfig(id="left"))
            rsrc = _SparkRight(_config=KnotConfig(id="right"))
            return SparkJoin(
                left=lsrc, right=rsrc, on="id", _config=KnotConfig(id="join"), **kwargs
            )

    async def test_rejects_invalid_how(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(
                left=_mock_sdf(["id", "a"]),
                right=_mock_sdf(["id", "b"]),
                on="id",
                left_on=None,
                right_on=None,
                how="full",
            )

    async def test_rejects_no_keys_for_non_cross(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                left=_mock_sdf(["id", "a"]),
                right=_mock_sdf(["id", "b"]),
                on=None,
                left_on=None,
                right_on=None,
                how="inner",
            )

    async def test_rejects_on_with_left_right(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                left=_mock_sdf(["id", "a"]),
                right=_mock_sdf(["id", "b"]),
                on="id",
                left_on="id",
                right_on="id",
                how="inner",
            )

    async def test_rejects_cross_with_on(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                left=_mock_sdf(["a"]),
                right=_mock_sdf(["b"]),
                on="id",
                left_on=None,
                right_on=None,
                how="cross",
            )
