"""Tests for :class:`TimeSeriesForecastingPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.time_series_forecasting_pipeline import (
    TimeSeriesForecastingPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_horizon(self) -> None:
        knot = TimeSeriesForecastingPipeline(
            pool=RecordingDatabasePool(rows=[(1.0, 1.0)]),
            query="SELECT 1",
            time_column="ts",
            target_column="y",
            feature_names=("a",),
            horizon=0,
            _config=KnotConfig(id="bad"),
        )
        with self.assertRaisesRegex(ValueError, "horizon"):
            await knot.process(
                pool=RecordingDatabasePool(rows=[(1.0, 1.0)]),
                query="SELECT 1",
                time_column="ts",
                target_column="y",
                feature_names=("a",),
                horizon=0,
            )

    async def test_rejects_empty_feature_names(self) -> None:
        knot = TimeSeriesForecastingPipeline(
            pool=RecordingDatabasePool(rows=[(1.0,)]),
            query="SELECT 1",
            time_column="ts",
            target_column="y",
            feature_names=(),
            _config=KnotConfig(id="bad"),
        )
        with self.assertRaisesRegex(ValueError, "feature_names"):
            await knot.process(
                pool=RecordingDatabasePool(rows=[(1.0,)]),
                query="SELECT 1",
                time_column="ts",
                target_column="y",
                feature_names=(),
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_eval_report(self) -> None:
        rows = [{"ts": i, "a": float(i), "y": float(i)} for i in range(40)]
        with Tapestry() as t:
            TimeSeriesForecastingPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT ts, a, y FROM data",
                time_column="ts",
                target_column="y",
                feature_names=("a",),
                horizon=3,
                _config=KnotConfig(id="tsfp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["tsfp"]
        assert isinstance(report, EvalReportPayload)
