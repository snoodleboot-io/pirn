"""Tests for :class:`SparkFilter`."""

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

from pirn.domains.data.lazy.spark.spark_filter import SparkFilter
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _mock_sdf() -> SparkDataFrame:
    frame = MagicMock()
    frame.columns = ["x", "y"]
    filtered = MagicMock()
    filtered.columns = ["x", "y"]
    frame.filter.return_value = filtered
    return SparkDataFrame(frame=frame)


class _SparkSource(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf()


class TestSparkFilterConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            flt = SparkFilter(frame=src, predicate="x > 0", _config=KnotConfig(id="flt"))
        self.assertEqual(flt.predicate, "x > 0")

    def test_rejects_non_string_predicate(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                SparkFilter(frame=src, predicate=123, _config=KnotConfig(id="flt"))  # type: ignore[arg-type]

    def test_rejects_empty_predicate(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(ValueError):
                SparkFilter(frame=src, predicate="  ", _config=KnotConfig(id="flt"))


class TestSparkFilterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_applies_filter_to_frame(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            flt = SparkFilter(frame=src, predicate="x > 0", _config=KnotConfig(id="flt"))
        result = await flt.process(frame=sdf)
        self.assertIsInstance(result, SparkDataFrame)
        sdf.frame.filter.assert_called_once_with("x > 0")
