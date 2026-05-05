"""Tests for :class:`SparkWriteSink`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn.domains.data.lazy.spark.spark_execution_receipt import SparkExecutionReceipt

try:
    import pyspark.sql  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyspark not installed") from _e

from pirn.domains.data.lazy.spark.spark_write_sink import SparkWriteSink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _mock_sdf() -> SparkDataFrame:
    frame = MagicMock()
    frame.columns = ["x"]
    writer = MagicMock()
    writer.mode.return_value = writer
    writer.format.return_value = writer
    writer.save.return_value = None
    frame.write = writer
    return SparkDataFrame(frame=frame)


class _SparkSource(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf()


class TestSparkWriteSinkConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkWriteSink(frame=src, path="/tmp/output", _config=KnotConfig(id="sink"))
        self.assertEqual(sink.path, "/tmp/output")
        self.assertEqual(sink.format, "parquet")
        self.assertEqual(sink.mode, "overwrite")

    def test_rejects_empty_path(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(ValueError):
                SparkWriteSink(frame=src, path="", _config=KnotConfig(id="sink"))

    def test_custom_format_and_mode(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkWriteSink(frame=src, path="/tmp/out", format="csv", mode="append", _config=KnotConfig(id="sink"))
        self.assertEqual(sink.format, "csv")
        self.assertEqual(sink.mode, "append")


class TestSparkWriteSinkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_receipt(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkWriteSink(frame=src, path="/tmp/output", _config=KnotConfig(id="sink"))
        result = await sink.process(frame=sdf)
        self.assertIsInstance(result, SparkExecutionReceipt)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.output_path, "/tmp/output")
        sdf.frame.write.mode.assert_called_once_with("overwrite")
