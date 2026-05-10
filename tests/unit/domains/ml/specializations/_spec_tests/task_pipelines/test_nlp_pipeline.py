"""Tests for :class:`NLPPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.nlp_pipeline import (
    NLPPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)
from tests.unit.domains.ml._stubs.recording_embedding_provider import (
    RecordingEmbeddingProvider,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_provider(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "embedding_provider"):
                NLPPipeline(
                    pool=RecordingDatabasePool(rows=[(1,)]),
                    query="SELECT 1",
                    text_column="text",
                    target_column="y",
                    embedding_provider="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_classification_report(self) -> None:
        rows = [("text " + str(i), i % 2) for i in range(40)]
        provider = RecordingEmbeddingProvider()
        with Tapestry() as t:
            NLPPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT text, y FROM data",
                text_column="text",
                target_column="y",
                embedding_provider=provider,
                algorithm="logistic",
                _config=KnotConfig(id="nlp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["nlp"]
        assert isinstance(report, EvalReportPayload)
        assert "f1" in report.metrics.scores
        # Embedding provider was probed.
        assert provider.calls
