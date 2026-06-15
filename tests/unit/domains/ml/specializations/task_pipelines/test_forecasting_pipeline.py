"""Unit tests for :class:`ForecastingPipeline`."""

from __future__ import annotations

import unittest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.task_pipelines.forecasting_pipeline import (
    ForecastingPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_time_column(self) -> None:
        with Tapestry():
            k = ForecastingPipeline.__new__(ForecastingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT 1",
                time_column="",
                target_column="sales",
                feature_names=["a"],
            )

    async def test_rejects_horizon_less_than_1(self) -> None:
        with Tapestry():
            k = ForecastingPipeline.__new__(ForecastingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT 1",
                time_column="ts",
                target_column="sales",
                feature_names=["a"],
                horizon=0,
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = ForecastingPipeline.__new__(ForecastingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT 1",
                time_column="ts",
                target_column="sales",
                feature_names=[],
            )
