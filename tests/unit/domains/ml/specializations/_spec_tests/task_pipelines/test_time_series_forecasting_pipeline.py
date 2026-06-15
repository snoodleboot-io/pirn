"""Tests for :class:`TimeSeriesForecastingPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.task_pipelines.time_series_forecasting_pipeline import (
    TimeSeriesForecastingPipeline,
)

from tests.unit.domains.ml._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = TimeSeriesForecastingPipeline.__new__(TimeSeriesForecastingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                time_column="ts",
                target_column="y",
                feature_names=("a",),
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = TimeSeriesForecastingPipeline.__new__(TimeSeriesForecastingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                time_column="ts",
                target_column="y",
                feature_names=(),
            )

    async def test_rejects_zero_horizon(self) -> None:
        with Tapestry():
            k = TimeSeriesForecastingPipeline.__new__(TimeSeriesForecastingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                time_column="ts",
                target_column="y",
                feature_names=("a",),
                horizon=0,
            )
