"""Tests for :class:`NamedEntityRecognitionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.named_entity_recognition_pipeline import (
    NamedEntityRecognitionPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_text_column(self) -> None:
        knot = NamedEntityRecognitionPipeline(
            pool=RecordingDatabasePool(rows=[("text", "O")]),
            query="SELECT 1",
            text_column="",
            label_column="label",
            _config=KnotConfig(id="bad"),
        )
        with self.assertRaisesRegex(ValueError, "text_column"):
            await knot.process(
                pool=RecordingDatabasePool(rows=[("text", "O")]),
                query="SELECT 1",
                text_column="",
                label_column="label",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_ner_report(self) -> None:
        rows = [(f"token {i}", "O" if i % 3 != 0 else "B-PER") for i in range(40)]
        with Tapestry() as t:
            NamedEntityRecognitionPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT token, label FROM data",
                text_column="token",
                label_column="label",
                _config=KnotConfig(id="ner"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["ner"]
        assert isinstance(report, EvalReportPayload)
        assert {"precision", "recall", "f1"}.issubset(report.metrics.scores.keys())
