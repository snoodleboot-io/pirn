"""Tests for :class:`SparkAggregate`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_data.lazy.spark.spark_dataframe import SparkDataFrame

try:
    import pyspark.sql  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyspark not installed") from _e

from pirn.nodes.source import Source
from pirn.tapestry import Tapestry
from pirn_data.lazy.spark.spark_aggregate import SparkAggregate


def _mock_sdf() -> SparkDataFrame:
    frame = MagicMock()
    frame.columns = ["region", "amount"]
    grouped = MagicMock()
    frame.groupBy.return_value = grouped
    grouped.agg.return_value = MagicMock()
    return SparkDataFrame(frame=frame)


def _mock_spark_functions() -> MagicMock:
    """Return a mock for pyspark.sql.functions that avoids JVM calls."""
    sf = MagicMock()
    col_expr = MagicMock()
    sf.sum.return_value = col_expr
    sf.count.return_value = col_expr
    sf.min.return_value = col_expr
    sf.max.return_value = col_expr
    sf.mean.return_value = col_expr
    col_expr.alias.return_value = col_expr
    return sf


class _SparkSource(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf()


class TestSparkAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_single_agg(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            agg = SparkAggregate(
                frame=src,
                by=["region"],
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="agg"),
            )
        mock_sf = _mock_spark_functions()
        import pyspark.sql as _psql
        with patch.object(_psql, "functions", mock_sf):
            result = await agg.process(
                frame=sdf,
                by=["region"],
                aggs={"total": ("amount", "sum")},
            )
        self.assertIsInstance(result, SparkDataFrame)
        sdf.frame.groupBy.assert_called_once_with("region")

    async def test_multiple_aggs(self) -> None:
        sdf = _mock_sdf()
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            agg = SparkAggregate(
                frame=src,
                by=["region"],
                aggs={"total": ("amount", "sum"), "cnt": ("amount", "count")},
                _config=KnotConfig(id="agg"),
            )
        mock_sf = _mock_spark_functions()
        import pyspark.sql as _psql
        with patch.object(_psql, "functions", mock_sf):
            result = await agg.process(
                frame=sdf,
                by=["region"],
                aggs={"total": ("amount", "sum"), "cnt": ("amount", "count")},
            )
        self.assertIsInstance(result, SparkDataFrame)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        @knot
        async def emit_by() -> list[str]:
            return ["region"]

        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            by_knot = emit_by(_config=KnotConfig(id="by"))
            SparkAggregate(
                frame=src,
                by=by_knot,
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="agg"),
            )
        # Construction with Knot input succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> SparkAggregate:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            return SparkAggregate(
                frame=src,
                by=["region"],
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="agg"),
                **kwargs,
            )

    async def test_rejects_empty_aggs(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(TypeError):
            await k.process(frame=_mock_sdf(), by=["region"], aggs={})

    async def test_rejects_invalid_fn(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(ValueError):
            await k.process(
                frame=_mock_sdf(),
                by=["region"],
                aggs={"total": ("amount", "not_valid_fn")},
            )

    async def test_rejects_malformed_agg_spec(self) -> None:
        k = await self._make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                frame=_mock_sdf(),
                by=["region"],
                aggs={"total": "not-a-tuple"},  # type: ignore[dict-item]
            )
