"""Tests for :class:`SparkAggregate`."""

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

from pirn.domains.data.lazy.spark.spark_aggregate import SparkAggregate
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _mock_sdf() -> SparkDataFrame:
    frame = MagicMock()
    frame.columns = ["region", "amount"]
    return SparkDataFrame(frame=frame)


class _SparkSource(Source):
    async def process(self, **_: Any) -> SparkDataFrame:
        return _mock_sdf()


class TestSparkAggregateConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            agg = SparkAggregate(
                frame=src,
                by=["region"],
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="agg"),
            )
        self.assertIsInstance(agg, SparkAggregate)
        self.assertEqual(agg.by, ("region",))

    def test_rejects_empty_aggs(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                SparkAggregate(frame=src, by=["region"], aggs={}, _config=KnotConfig(id="agg"))

    def test_rejects_invalid_fn(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(ValueError):
                SparkAggregate(
                    frame=src,
                    by=["region"],
                    aggs={"total": ("amount", "not_valid_fn")},
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_malformed_agg_spec(self) -> None:
        with Tapestry():
            src = _SparkSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                SparkAggregate(
                    frame=src,
                    by=["region"],
                    aggs={"total": "not-a-tuple"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="agg"),
                )
