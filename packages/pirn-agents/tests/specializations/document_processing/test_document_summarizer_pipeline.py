"""Tests for :class:`DocumentSummarizerPipeline`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing.document_summarizer_pipeline import (
    DocumentSummarizerPipeline,
)
from tests.specializations.conftest import (
    StubLLMProvider,
)


def _make_knot(llm: StubLLMProvider) -> DocumentSummarizerPipeline:
    with Tapestry():
        return DocumentSummarizerPipeline(
            source="/tmp/placeholder.txt",
            llm=llm,
            _config=KnotConfig(id="summ"),
        )


class TestDocumentSummarizerPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_chunk_size(self) -> None:
        llm = StubLLMProvider(["summary"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(ValueError, "chunk_size"):
            await k.process(source="/tmp/x.txt", llm=llm, chunk_size=0)

    async def test_returns_reduced_summary(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        document = tmp_path / "doc.txt"
        document.write_text("alpha beta gamma delta epsilon", encoding="utf-8")
        llm = StubLLMProvider(
            [
                "chunk-1 summary",
                "chunk-2 summary",
                "combined summary",
            ]
        )
        with Tapestry() as t:
            DocumentSummarizerPipeline(
                source=str(document),
                llm=llm,
                chunk_size=15,
                _config=KnotConfig(id="summ"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        summary = result.outputs["summ"]
        assert summary == "combined summary"
        # 2 map calls + 1 reduce call.
        assert len(llm.calls) == 3
