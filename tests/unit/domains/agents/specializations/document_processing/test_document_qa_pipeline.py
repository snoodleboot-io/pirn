"""Tests for :class:`DocumentQAPipeline`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing.document_qa_pipeline import (
    DocumentQAPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubEmbeddingProvider,
    StubLLMProvider,
)


def _make_knot(llm: StubLLMProvider, embedder: StubEmbeddingProvider) -> DocumentQAPipeline:
    with Tapestry():
        return DocumentQAPipeline(
            source="/tmp/placeholder.txt",
            question="?",
            llm=llm,
            embedder=embedder,
            top_k=3,
            _config=KnotConfig(id="qa"),
        )


class TestDocumentQAPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_top_k(self) -> None:
        llm = StubLLMProvider(["answer"])
        embedder = StubEmbeddingProvider()
        k = _make_knot(llm, embedder)
        with self.assertRaisesRegex(ValueError, "top_k"):
            await k.process(
                source="/tmp/x.txt",
                question="?",
                llm=llm,
                embedder=embedder,
                top_k=0,
            )

    async def test_returns_agent_response(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        document = tmp_path / "doc.txt"
        document.write_text(
            "Alpha facts. Beta facts. Gamma facts.",
            encoding="utf-8",
        )
        llm = StubLLMProvider(["The answer is alpha."])
        embedder = StubEmbeddingProvider(dimension=3)
        with Tapestry() as t:
            DocumentQAPipeline(
                source=str(document),
                question="What are the alpha facts?",
                llm=llm,
                embedder=embedder,
                top_k=2,
                _config=KnotConfig(id="qa"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["qa"]
        assert isinstance(response, AgentResponse)
        assert response.content == "The answer is alpha."
        assert response.finish_reason == "stop"
        assert len(llm.calls) == 1
        prompt_body = llm.calls[0][-1]["content"]
        assert "Document excerpts" in prompt_body
        assert "alpha facts" in prompt_body.lower()
