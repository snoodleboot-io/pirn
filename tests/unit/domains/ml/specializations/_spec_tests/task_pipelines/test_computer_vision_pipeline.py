"""Tests for :class:`ComputerVisionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.computer_vision_pipeline import (
    ComputerVisionPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)
from tests.unit.domains.ml._stubs.recording_image_encoder_provider import (
    RecordingImageEncoderProvider,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_image_encoder(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "image_encoder"):
                ComputerVisionPipeline(
                    pool=RecordingDatabasePool(rows=[(b"img", 0)]),
                    query="SELECT 1",
                    image_column="img",
                    target_column="y",
                    image_encoder="not-an-encoder",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_classification_report(self) -> None:
        rows = [(b"image-bytes-" + str(i).encode(), i % 2) for i in range(40)]
        encoder = RecordingImageEncoderProvider()
        with Tapestry() as t:
            ComputerVisionPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT img, y FROM data",
                image_column="img",
                target_column="y",
                image_encoder=encoder,
                algorithm="logistic",
                _config=KnotConfig(id="cv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["cv"]
        assert isinstance(report, EvalReportPayload)
        assert "f1" in report.metrics.scores
        # Image encoder was probed.
        assert encoder.calls
