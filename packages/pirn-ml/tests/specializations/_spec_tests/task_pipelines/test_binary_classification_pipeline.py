"""Tests for :class:`BinaryClassificationPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.task_pipelines.binary_classification_pipeline import (
    BinaryClassificationPipeline,
)
from pirn_ml.types.eval_report_payload import EvalReportPayload

from tests._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_target_column(self) -> None:
        with Tapestry():
            k = BinaryClassificationPipeline.__new__(BinaryClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1, 0)]),
                query="SELECT 1",
                target_column="",
                feature_names=("a",),
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = BinaryClassificationPipeline.__new__(BinaryClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1, 0)]),
                query="SELECT 1",
                target_column="y",
                feature_names=(),
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_classification_report(self) -> None:
        rows = [{"a": float(i), "y": i % 2} for i in range(40)]
        with Tapestry() as t:
            BinaryClassificationPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, y FROM data",
                target_column="y",
                feature_names=("a",),
                algorithm="logistic",
                _config=KnotConfig(id="bin"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["bin"]
        assert isinstance(report, EvalReportPayload)
        assert "accuracy" in report.metrics.scores
        assert "f1" in report.metrics.scores
        assert "roc_auc" in report.metrics.scores
