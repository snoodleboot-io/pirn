"""Tests for :class:`RAGSynthesizer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@pytest.mark.asyncio
class TestRAGSynthesizerConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                RAGSynthesizer(
                    query="q",
                    documents=[],
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="synth"),
                )


@pytest.mark.asyncio
class TestRAGSynthesizerHappyPath:
    async def test_synthesizes_answer_from_documents(self) -> None:
        docs = [
            {"text": "The capital of France is Paris."},
            {"text": "Paris has a population of 2 million."},
        ]
        llm = StubLLMProvider(["Paris is the capital [1]. It has 2M people [2]."])
        with Tapestry() as t:
            RAGSynthesizer(
                query="Tell me about France's capital.",
                documents=docs,
                llm=llm,
                _config=KnotConfig(id="synth"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["synth"]
        assert isinstance(response, AgentResponse)
        assert "Paris" in response.content
        assert response.finish_reason == "stop"

    async def test_handles_empty_documents(self) -> None:
        llm = StubLLMProvider(["I cannot find relevant information."])
        with Tapestry() as t:
            RAGSynthesizer(
                query="What is X?",
                documents=[],
                llm=llm,
                _config=KnotConfig(id="synth"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["synth"]
        assert isinstance(response, AgentResponse)
        prompt_sent = llm.calls[0][-1]["content"]
        assert "no documents retrieved" in prompt_sent

    async def test_includes_sources_in_prompt(self) -> None:
        docs = [{"text": "relevant passage"}]
        llm = StubLLMProvider(["The answer is here [1]."])
        with Tapestry() as t:
            RAGSynthesizer(
                query="What is relevant?",
                documents=docs,
                llm=llm,
                _config=KnotConfig(id="synth"),
            )
        await t.run(RunRequest())
        prompt_sent = llm.calls[0][-1]["content"]
        assert "[1]" in prompt_sent
        assert "relevant passage" in prompt_sent
