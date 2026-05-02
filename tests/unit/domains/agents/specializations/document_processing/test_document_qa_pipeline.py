"""Tests for :class:`DocumentQAPipeline`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing.document_qa_pipeline import (  # noqa: E501
    DocumentQAPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubEmbeddingProvider,
    StubLLMProvider,
)


@pytest.mark.asyncio
class TestDocumentQAPipelineConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        embedder = StubEmbeddingProvider()
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                DocumentQAPipeline(
                    source="/tmp/x.txt",
                    question="?",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    embedder=embedder,
                    _config=KnotConfig(id="qa"),
                )

    async def test_rejects_zero_top_k(self) -> None:
        llm = StubLLMProvider(["answer"])
        embedder = StubEmbeddingProvider()
        with pytest.raises(ValueError, match="top_k"):
            with Tapestry():
                DocumentQAPipeline(
                    source="/tmp/x.txt",
                    question="?",
                    llm=llm,
                    embedder=embedder,
                    top_k=0,
                    _config=KnotConfig(id="qa"),
                )


@pytest.mark.asyncio
class TestDocumentQAPipelineHappyPath:
    async def test_returns_agent_response(self, tmp_path: Path) -> None:
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
