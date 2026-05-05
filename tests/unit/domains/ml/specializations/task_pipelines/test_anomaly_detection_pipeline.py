"""Tests for :class:`AnomalyDetectionPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.anomaly_detection_pipeline import (
    AnomalyDetectionPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "algorithm"):
                AnomalyDetectionPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0, 2.0)]),
                    query="SELECT 1",
                    feature_names=("a",),
                    algorithm="svm",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_contamination_out_of_range(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "contamination"):
                AnomalyDetectionPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0,)]),
                    query="SELECT 1",
                    feature_names=("a",),
                    contamination=0.6,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_anomaly_report(self) -> None:
        rows = [(float(i), float(i)) for i in range(40)]
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
        report: EvalReport = result.outputs["adp"]
        assert isinstance(report, EvalReport)
