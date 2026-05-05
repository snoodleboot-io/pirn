"""Tests for :class:`SparkCollectSink`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
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


class TestSparkCollectSink(unittest.IsolatedAsyncioTestCase):
    async def test_collects_all_rows(self) -> None:
        sdf = _mock_sdf([{"id": 1}, {"id": 2}])
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkCollectSink(frame=src, _config=KnotConfig(id="sink"))
        result = await sink.process(frame=sdf, max_rows=None)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1)

    async def test_max_rows_not_exceeded(self) -> None:
        sdf = _mock_sdf([{"id": 1}, {"id": 2}])
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkCollectSink(frame=src, max_rows=5, _config=KnotConfig(id="sink"))
        result = await sink.process(frame=sdf, max_rows=5)
        self.assertEqual(len(result), 2)

    async def test_max_rows_exceeded_raises(self) -> None:
        sdf = _mock_sdf([{"id": i} for i in range(5)])
        limited = MagicMock()
        limited.collect.return_value = [_row({"id": i}) for i in range(3)]
        sdf.frame.limit = MagicMock(return_value=limited)
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            sink = SparkCollectSink(frame=src, max_rows=2, _config=KnotConfig(id="sink"))
        with self.assertRaises(ValueError):
            await sink.process(frame=sdf, max_rows=2)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_max_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_limit() -> int:
            return 100

        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            limit_knot = emit_limit(_config=KnotConfig(id="limit"))
            SparkCollectSink(frame=src, max_rows=limit_knot, _config=KnotConfig(id="sink"))
        # Construction with Knot input succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> SparkCollectSink:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            return SparkCollectSink(frame=src, _config=KnotConfig(id="sink"), **kwargs)

    async def test_rejects_non_int_max_rows(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(TypeError):
            await k.process(frame=_mock_sdf([{"id": 1}]), max_rows="100")  # type: ignore[arg-type]

    async def test_rejects_zero_max_rows(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(frame=_mock_sdf([{"id": 1}]), max_rows=0)

    async def test_rejects_negative_max_rows(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(frame=_mock_sdf([{"id": 1}]), max_rows=-1)
