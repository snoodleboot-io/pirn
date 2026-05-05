"""Tests for :class:`GoldAggregation`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.medallion.gold_aggregation import (
    GoldAggregation,
)
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec


def _make_pool() -> MagicMock:
    return MagicMock(spec=DatabaseConnectionPool)


class TestGoldAggregationConstruction(unittest.TestCase):
    def _make_valid(self) -> GoldAggregation:
        return GoldAggregation(
            source_pool=_make_pool(),
            source_query="SELECT region, amount FROM silver_sales",
            source_columns=["region", "amount"],
            target_pool=_make_pool(),
            target_table="gold_sales",
            by=["region"],
            aggs={"total": AggregateSpec(source="amount", function="sum")},
            _config=KnotConfig(id="gold"),
        )

    def test_valid_construction(self) -> None:
        ga = self._make_valid()
        self.assertIsInstance(ga, GoldAggregation)

    def test_rejects_non_pool_source(self) -> None:
        with self.assertRaises(TypeError):
            GoldAggregation(
                source_pool="not-pool",  # type: ignore[arg-type]
                source_query="SELECT 1",
                source_columns=["a"],
                target_pool=_make_pool(),
                target_table="gold",
                by=["a"],
                aggs={"tot": AggregateSpec(source="a", function="sum")},
                _config=KnotConfig(id="gold"),
            )

    def test_rejects_empty_source_columns(self) -> None:
        with self.assertRaises(ValueError):
            GoldAggregation(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                source_columns=[],
                target_pool=_make_pool(),
                target_table="gold",
                by=["a"],
                aggs={"tot": AggregateSpec(source="a", function="sum")},
                _config=KnotConfig(id="gold"),
            )

    def test_rejects_empty_by(self) -> None:
        with self.assertRaises(ValueError):
            GoldAggregation(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                source_columns=["a"],
                target_pool=_make_pool(),
                target_table="gold",
                by=[],
                aggs={"tot": AggregateSpec(source="a", function="sum")},
                _config=KnotConfig(id="gold"),
            )

    def test_insert_query_references_target_table(self) -> None:
        ga = self._make_valid()
        self.assertIn("gold_sales", ga._insert_query)
