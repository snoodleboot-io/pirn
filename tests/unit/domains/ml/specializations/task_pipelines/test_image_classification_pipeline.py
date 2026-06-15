"""Tests for :class:`ImageClassificationPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.image_classification_pipeline import (
    ImageClassificationPipeline,
)
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry

from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_architecture(self) -> None:
        knot = ImageClassificationPipeline(
            pool=RecordingDatabasePool(rows=[(b"img", 0)]),
            query="SELECT 1",
            image_column="img",
            label_column="label",
            architecture="resnet",
            _config=KnotConfig(id="bad"),
        )
        with self.assertRaisesRegex(ValueError, "architecture"):
            await knot.process(
                pool=RecordingDatabasePool(rows=[(b"img", 0)]),
                query="SELECT 1",
                image_column="img",
                label_column="label",
                architecture="resnet",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_classification_report(self) -> None:
        rows = [{"img": float(i), "label": i % 3} for i in range(40)]
        with Tapestry() as t:
            ImageClassificationPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT img, label FROM data",
                image_column="img",
                label_column="label",
                architecture="cnn",
                _config=KnotConfig(id="icp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["icp"]
        assert isinstance(report, EvalReportPayload)
        assert "accuracy" in report.metrics.scores
