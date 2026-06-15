"""Tests for :class:`MetricLayerAggregator`."""

from __future__ import annotations

import unittest
from typing import Any

import pytest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.analytics_engineering.metric_layer_aggregator import (
    MetricLayerAggregator,
)

_SOURCE_TABLE = "sales"
_METRIC_NAME = "total_revenue"
_AGGREGATION = "sum"
_VALUE_COLUMN = "amount"


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE sales (region TEXT, amount REAL, num INTEGER)")
    await p.execute_many(
        "INSERT INTO sales VALUES (?, ?, ?)",
        [("EU", 100.0, 2), ("EU", 50.0, 1), ("US", 200.0, 4)],
    )
    return p


def _make_knot(pool: SqlitePool) -> MetricLayerAggregator:
    return MetricLayerAggregator(
        pool=pool,
        source_table=_SOURCE_TABLE,
        metric_name=_METRIC_NAME,
        aggregation=_AGGREGATION,
        value_column=_VALUE_COLUMN,
        _config=KnotConfig(id="m"),
    )


class TestMetricLayerAggregator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_sum_without_dimensions(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["m"]
        assert output["metric_name"] == _METRIC_NAME
        assert output["value"] == pytest.approx(350.0)
        assert output["dimensions"] == []

    async def test_sum_with_dimension_slicing(self) -> None:
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=self.pool,
                source_table=_SOURCE_TABLE,
                metric_name="revenue_by_region",
                aggregation="sum",
                value_column="amount",
                dimension_columns=("region",),
                _config=KnotConfig(id="m-dim"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["m-dim"]
        assert output["metric_name"] == "revenue_by_region"
        assert isinstance(output["value"], list)
        assert len(output["value"]) == 2

    async def test_count_aggregation(self) -> None:
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=self.pool,
                source_table=_SOURCE_TABLE,
                metric_name="row_count",
                aggregation="count",
                value_column="amount",
                _config=KnotConfig(id="m-cnt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["m-cnt"]["value"] == 3

    async def test_avg_aggregation(self) -> None:
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=self.pool,
                source_table=_SOURCE_TABLE,
                metric_name="avg_amount",
                aggregation="avg",
                value_column="amount",
                _config=KnotConfig(id="m-avg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["m-avg"]["value"] == pytest.approx(350.0 / 3)

    async def test_ratio_aggregation(self) -> None:
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=self.pool,
                source_table=_SOURCE_TABLE,
                metric_name="avg_amount_per_unit",
                aggregation="ratio",
                value_column="amount",
                numerator_column="amount",
                denominator_column="num",
                _config=KnotConfig(id="m-rat"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["m-rat"]["value"] == pytest.approx(350.0 / 7)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_metric_name_from_upstream_knot(self) -> None:
        @knot
        async def emit_name() -> str:
            return _METRIC_NAME

        with Tapestry() as t:
            name_knot = emit_name(_config=KnotConfig(id="name"))
            MetricLayerAggregator(
                pool=self.pool,
                source_table=_SOURCE_TABLE,
                metric_name=name_knot,
                aggregation=_AGGREGATION,
                value_column=_VALUE_COLUMN,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["m"]["metric_name"] == _METRIC_NAME


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> MetricLayerAggregator:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "source_table": _SOURCE_TABLE,
            "metric_name": _METRIC_NAME,
            "aggregation": _AGGREGATION,
            "value_column": _VALUE_COLUMN,
        }
        defaults.update(kwargs)
        with Tapestry():
            return MetricLayerAggregator(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: MetricLayerAggregator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "source_table": _SOURCE_TABLE,
            "metric_name": _METRIC_NAME,
            "aggregation": _AGGREGATION,
            "value_column": _VALUE_COLUMN,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_invalid_aggregation(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "aggregation"):
            await self._call(k, aggregation="median")

    async def test_ratio_requires_numerator_denominator(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "ratio"):
            await self._call(k, aggregation="ratio", numerator_column="", denominator_column="")

    async def test_rejects_empty_source_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_table"):
            await self._call(k, source_table="")
