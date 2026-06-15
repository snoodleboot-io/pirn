"""Tests for :class:`SparkWriteSink`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn_data.lazy.spark.spark_execution_receipt import SparkExecutionReceipt

try:
    import pyspark.sql  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyspark not installed") from _e

from pirn.nodes.source import Source
from pirn.tapestry import Tapestry
from pirn_data.lazy.spark.spark_write_sink import SparkWriteSink


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


class TestSparkWriteSink(unittest.IsolatedAsyncioTestCase):
    async def test_returns_receipt_with_defaults(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkWriteSink(frame=src, path="/tmp/output", _config=KnotConfig(id="sink"))
        result = await sink.process(
            frame=sdf,
            path="/tmp/output",
            format="parquet",
            mode="overwrite",
        )
        self.assertIsInstance(result, SparkExecutionReceipt)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.output_path, "/tmp/output")
        sdf.frame.write.mode.assert_called_once_with("overwrite")
        sdf.frame.write.mode().format.assert_called_once_with("parquet")

    async def test_custom_format_and_mode(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkWriteSink(
                frame=src,
                path="/tmp/out",
                format="csv",
                mode="append",
                _config=KnotConfig(id="sink"),
            )
        result = await sink.process(
            frame=sdf,
            path="/tmp/out",
            format="csv",
            mode="append",
        )
        self.assertIsInstance(result, SparkExecutionReceipt)
        self.assertEqual(result.output_path, "/tmp/out")


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_path_from_upstream_knot(self) -> None:
        @knot
        async def emit_path() -> str:
            return "/tmp/dynamic"

        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            path_knot = emit_path(_config=KnotConfig(id="path"))
            SparkWriteSink(frame=src, path=path_knot, _config=KnotConfig(id="sink"))
        # Construction with Knot input succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> SparkWriteSink:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            return SparkWriteSink(
                frame=src, path="/tmp/out", _config=KnotConfig(id="sink"), **kwargs
            )

    async def test_rejects_empty_path(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(frame=_mock_sdf(), path="", format="parquet", mode="overwrite")

    async def test_rejects_empty_format(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(frame=_mock_sdf(), path="/tmp/out", format="", mode="overwrite")

    async def test_rejects_empty_mode(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(frame=_mock_sdf(), path="/tmp/out", format="parquet", mode="")
