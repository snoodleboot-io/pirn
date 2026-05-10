"""Tests for :class:`TextClassificationPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.text_classification_pipeline import (
    TextClassificationPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_vectorizer(self) -> None:
        knot = TextClassificationPipeline(
            pool=RecordingDatabasePool(rows=[("text", 1)]),
            query="SELECT 1",
            text_column="text",
            target_column="label",
            vectorizer="word2vec",
            _config=KnotConfig(id="bad"),
        )
        with self.assertRaisesRegex(ValueError, "vectorizer"):
            await knot.process(
                pool=RecordingDatabasePool(rows=[("text", 1)]),
                query="SELECT 1",
                text_column="text",
                target_column="label",
                vectorizer="word2vec",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_classification_report(self) -> None:
        rows = [(f"text {i}", i % 2) for i in range(40)]
        with Tapestry() as t:
            TextClassificationPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT text, label FROM data",
                text_column="text",
                target_column="label",
                vectorizer="tfidf",
                _config=KnotConfig(id="tc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["tc"]
        assert isinstance(report, EvalReportPayload)
        assert {"accuracy", "f1"}.issubset(report.metrics.scores.keys())
