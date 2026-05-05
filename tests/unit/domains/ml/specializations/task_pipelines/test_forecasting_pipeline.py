"""Unit tests for :class:`ForecastingPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.ml.specializations.task_pipelines.forecasting_pipeline import (
    ForecastingPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_time_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ForecastingPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    time_column="",
                    target_column="sales",
                    feature_names=["a"],
                    _config=KnotConfig(id="fp"),
                )

    def test_rejects_horizon_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ForecastingPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    time_column="ts",
                    target_column="sales",
                    feature_names=["a"],
                    horizon=0,
                    _config=KnotConfig(id="fp"),
                )

    def test_rejects_empty_feature_names(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ForecastingPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    time_column="ts",
                    target_column="sales",
                    feature_names=[],
                    _config=KnotConfig(id="fp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            ForecastingPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                time_column="ts",
                target_column="sales",
                feature_names=["a", "b"],
                horizon=7,
                _config=KnotConfig(id="fp"),
            )
        self.assertIsNotNone(t._store.get("fp"))
