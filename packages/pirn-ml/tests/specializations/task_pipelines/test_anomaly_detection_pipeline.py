"""Tests for :class:`AnomalyDetectionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.task_pipelines.anomaly_detection_pipeline import (
    AnomalyDetectionPipeline,
)
from pirn_ml.types.eval_report_payload import EvalReportPayload

from tests._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            k = AnomalyDetectionPipeline.__new__(AnomalyDetectionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0, 2.0)]),
                query="SELECT 1",
                feature_names=("a",),
                algorithm="svm",
            )

    async def test_rejects_contamination_out_of_range(self) -> None:
        with Tapestry():
            k = AnomalyDetectionPipeline.__new__(AnomalyDetectionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0,)]),
                query="SELECT 1",
                feature_names=("a",),
                contamination=0.6,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_anomaly_report(self) -> None:
        rows = [{"a": float(i), "b": float(i)} for i in range(40)]
        with Tapestry() as t:
            AnomalyDetectionPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, b FROM data",
                feature_names=("a",),
                algorithm="isolation_forest",
                _config=KnotConfig(id="adp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["adp"]
        assert isinstance(report, EvalReportPayload)
