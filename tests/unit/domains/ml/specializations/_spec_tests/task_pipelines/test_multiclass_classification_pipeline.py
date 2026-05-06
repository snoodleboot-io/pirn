"""Tests for :class:`MulticlassClassificationPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.multiclass_classification_pipeline import (
    MulticlassClassificationPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_classes_below_three(self) -> None:
        with Tapestry():
            k = MulticlassClassificationPipeline.__new__(MulticlassClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1, 0)]),
                query="SELECT 1",
                target_column="y",
                feature_names=("a",),
                n_classes=2,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_macro_metric_report(self) -> None:
        rows = [(float(i), i % 5) for i in range(40)]
        with Tapestry() as t:
            MulticlassClassificationPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, y FROM data",
                target_column="y",
                feature_names=("a",),
                n_classes=5,
                _config=KnotConfig(id="mc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["mc"]
        assert isinstance(report, EvalReport)
        assert "f1_macro" in report.metrics
        assert "precision_macro" in report.metrics
