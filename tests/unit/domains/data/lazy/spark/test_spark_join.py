"""Tests for :class:`SparkJoin`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame

try:
    import pyspark.sql  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyspark not installed") from _e

from pirn.domains.data.lazy.spark.spark_join import SparkJoin
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _mock_sdf(cols: list[str] | None = None) -> SparkDataFrame:
    frame = MagicMock()
    frame.columns = cols or ["id", "val"]
    return SparkDataFrame(frame=frame)


class _SparkLeft(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf(["id", "a"])


class _SparkRight(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf(["id", "b"])


class TestSparkJoinConstruction(unittest.TestCase):
    def test_valid_on_join(self) -> None:
        with Tapestry():
            left = _SparkLeft(_config=KnotConfig(id="left"))
            right = _SparkRight(_config=KnotConfig(id="right"))
            j = SparkJoin(left=left, right=right, on="id", _config=KnotConfig(id="join"))
        self.assertEqual(j.how, "inner")

    def test_cross_join(self) -> None:
        with Tapestry():
            left = _SparkLeft(_config=KnotConfig(id="left"))
            right = _SparkRight(_config=KnotConfig(id="right"))
            j = SparkJoin(left=left, right=right, how="cross", _config=KnotConfig(id="join"))
        self.assertEqual(j.how, "cross")

    def test_rejects_invalid_how(self) -> None:
        with Tapestry():
            left = _SparkLeft(_config=KnotConfig(id="left"))
            right = _SparkRight(_config=KnotConfig(id="right"))
            with self.assertRaises(ValueError):
                SparkJoin(left=left, right=right, on="id", how="full", _config=KnotConfig(id="join"))

    def test_rejects_no_keys_for_non_cross(self) -> None:
        with Tapestry():
            left = _SparkLeft(_config=KnotConfig(id="left"))
            right = _SparkRight(_config=KnotConfig(id="right"))
            with self.assertRaises(TypeError):
                SparkJoin(left=left, right=right, _config=KnotConfig(id="join"))

    def test_rejects_on_with_left_right(self) -> None:
        with Tapestry():
            left = _SparkLeft(_config=KnotConfig(id="left"))
            right = _SparkRight(_config=KnotConfig(id="right"))
            with self.assertRaises(TypeError):
                SparkJoin(left=left, right=right, on="id", left_on="id", right_on="id", _config=KnotConfig(id="join"))

    def test_cross_with_on_raises(self) -> None:
        with Tapestry():
            left = _SparkLeft(_config=KnotConfig(id="left"))
            right = _SparkRight(_config=KnotConfig(id="right"))
            with self.assertRaises(TypeError):
                SparkJoin(left=left, right=right, how="cross", on="id", _config=KnotConfig(id="join"))
