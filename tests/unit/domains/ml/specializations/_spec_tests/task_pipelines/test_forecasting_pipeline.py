"""Tests for :class:`ForecastingPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.forecasting_pipeline import (
    ForecastingPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_horizon(self) -> None:
        with Tapestry():
            k = ForecastingPipeline.__new__(ForecastingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0, 1.0, 1.0)]),
                query="SELECT 1",
                time_column="ts",
                target_column="y",
                feature_names=("a",),
                horizon=0,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_forecasting_report(self) -> None:
        rows = [(i, float(i), float(i)) for i in range(40)]
        with Tapestry() as t:
            ForecastingPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT ts, a, y FROM data",
                time_column="ts",
                target_column="y",
                feature_names=("a",),
                horizon=7,
                _config=KnotConfig(id="fc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["fc"]
        assert isinstance(report, EvalReportPayload)
        assert {"mape", "smape", "mase"}.issubset(report.metrics.scores.keys())
        assert report.metrics.details["time_column"] == "ts"
