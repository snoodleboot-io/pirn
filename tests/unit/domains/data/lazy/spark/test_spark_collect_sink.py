"""Tests for :class:`SparkCollectSink`."""

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

from pirn.domains.data.lazy.spark.spark_collect_sink import SparkCollectSink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _row(data: dict) -> MagicMock:
    row = MagicMock()
    row.asDict.return_value = data
    return row


def _mock_sdf(rows: list) -> SparkDataFrame:
    frame = MagicMock()
    frame.columns = list(rows[0].keys()) if rows else []
    frame.collect.return_value = [_row(r) for r in rows]

    def _limit(n: int) -> MagicMock:
        limited = MagicMock()
        limited.collect.return_value = [_row(r) for r in rows[:n]]
        return limited

    frame.limit = _limit
    return SparkDataFrame(frame=frame)


class _SparkSource(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf([{"id": 1}])


class TestSparkCollectSinkConstruction(unittest.TestCase):
    def test_valid_no_max_rows(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkCollectSink(frame=src, _config=KnotConfig(id="sink"))
        self.assertIsNone(sink.max_rows)

    def test_valid_with_max_rows(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkCollectSink(frame=src, max_rows=100, _config=KnotConfig(id="sink"))
        self.assertEqual(sink.max_rows, 100)

    def test_rejects_non_int_max_rows(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                SparkCollectSink(
                    frame=src,
                    max_rows="100",  # type: ignore[arg-type]
                    _config=KnotConfig(id="sink"),
                )

    def test_rejects_zero_max_rows(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(ValueError):
                SparkCollectSink(frame=src, max_rows=0, _config=KnotConfig(id="sink"))


class TestSparkCollectSinkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_collects_all_rows(self) -> None:
        sdf = _mock_sdf([{"id": 1}, {"id": 2}])
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkCollectSink(frame=src, _config=KnotConfig(id="sink"))
        result = await sink.process(frame=sdf)
        self.assertEqual(len(result), 2)

    async def test_max_rows_enforced(self) -> None:
        sdf = _mock_sdf([{"id": i} for i in range(5)])
        limited = MagicMock()
        limited.collect.return_value = [_row({"id": i}) for i in range(3)]
        sdf.frame.limit = MagicMock(return_value=limited)
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkCollectSink(frame=src, max_rows=2, _config=KnotConfig(id="sink"))
        with self.assertRaises(ValueError):
            await sink.process(frame=sdf)
