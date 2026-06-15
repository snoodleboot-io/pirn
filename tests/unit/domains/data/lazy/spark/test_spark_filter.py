"""Tests for :class:`SparkFilter`."""

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
from pirn_data.lazy.spark.spark_filter import SparkFilter


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


class TestSparkFilter(unittest.IsolatedAsyncioTestCase):
    async def test_applies_filter_happy_path(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            flt = SparkFilter(frame=src, predicate="x > 0", _config=KnotConfig(id="flt"))
        result = await flt.process(frame=sdf, predicate="x > 0")
        self.assertIsInstance(result, SparkDataFrame)
        sdf.frame.filter.assert_called_once_with("x > 0")

    async def test_compound_predicate(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            flt = SparkFilter(
                frame=src,
                predicate="x > 0 AND y = 'EU'",
                _config=KnotConfig(id="flt"),
            )
        result = await flt.process(frame=sdf, predicate="x > 0 AND y = 'EU'")
        self.assertIsInstance(result, SparkDataFrame)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        @knot
        async def emit_pred() -> str:
            return "x > 0"

        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            pred_knot = emit_pred(_config=KnotConfig(id="pred"))
            SparkFilter(frame=src, predicate=pred_knot, _config=KnotConfig(id="flt"))
        # Construction with Knot input succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> SparkFilter:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            return SparkFilter(
                frame=src,
                predicate="x > 0",
                _config=KnotConfig(id="flt"),
                **kwargs,
            )

    async def test_rejects_non_string_predicate(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(TypeError):
            await k.process(frame=_mock_sdf(), predicate=123)  # type: ignore[arg-type]

    async def test_rejects_empty_predicate(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(frame=_mock_sdf(), predicate="  ")

    async def test_rejects_empty_string_predicate(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(frame=_mock_sdf(), predicate="")
