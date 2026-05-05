"""Tests for :class:`MetricLayerAggregator`."""

from __future__ import annotations
import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.metric_layer_aggregator import (
    MetricLayerAggregator,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE sales (region TEXT, amount REAL, num INTEGER)"
        )
        await p.execute_many(
            "INSERT INTO sales VALUES (?, ?, ?)",
            [("EU", 100.0, 2), ("EU", 50.0, 1), ("US", 200.0, 4)],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    def test_rejects_invalid_aggregation(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "aggregation"):
            MetricLayerAggregator(
                pool=pool,
                source_table="sales",
                metric_name="total",
                aggregation="median",  # type: ignore[arg-type]
                value_column="amount",
                _config=KnotConfig(id="m"),
            )

    def test_ratio_requires_numerator_denominator(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "ratio"):
            MetricLayerAggregator(
                pool=pool,
                source_table="sales",
                metric_name="ratio",
                aggregation="ratio",
                value_column="amount",
                _config=KnotConfig(id="m"),
            )


class TestBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE sales (region TEXT, amount REAL, num INTEGER)"
        )
        await p.execute_many(
            "INSERT INTO sales VALUES (?, ?, ?)",
            [("EU", 100.0, 2), ("EU", 50.0, 1), ("US", 200.0, 4)],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_sum_without_dimensions(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=pool,
                source_table="sales",
                metric_name="total_revenue",
                aggregation="sum",
                value_column="amount",
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["m"]
        assert output["metric_name"] == "total_revenue"
        assert output["value"] == pytest.approx(350.0)
        assert output["dimensions"] == []

    async def test_sum_with_dimension_slicing(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=pool,
                source_table="sales",
                metric_name="revenue_by_region",
                aggregation="sum",
                value_column="amount",
                dimension_columns=["region"],
                _config=KnotConfig(id="m-dim"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["m-dim"]
        assert output["metric_name"] == "revenue_by_region"
        assert isinstance(output["value"], list)
        assert len(output["value"]) == 2

    async def test_count_aggregation(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=pool,
                source_table="sales",
                metric_name="row_count",
                aggregation="count",
                value_column="amount",
                _config=KnotConfig(id="m-cnt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["m-cnt"]["value"] == 3

    async def test_avg_aggregation(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=pool,
                source_table="sales",
                metric_name="avg_amount",
                aggregation="avg",
                value_column="amount",
                _config=KnotConfig(id="m-avg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["m-avg"]["value"] == pytest.approx(350.0 / 3)

    async def test_ratio_aggregation(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            MetricLayerAggregator(
                pool=pool,
                source_table="sales",
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
