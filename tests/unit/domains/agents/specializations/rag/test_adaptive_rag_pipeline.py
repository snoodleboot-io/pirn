"""Tests for :class:`AdaptiveRAGPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.adaptive_rag_pipeline import (
    AdaptiveRAGPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


@pytest.mark.asyncio
class TestAdaptiveRAGPipelineConstruction:
    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["SIMPLE", "answer"])
        with pytest.raises(TypeError, match="memory must be a MemoryStore"):
            with Tapestry():
                AdaptiveRAGPipeline(
                    query="q",
                    memory="bad",  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="adaptive"),
                )

    async def test_rejects_non_llm_provider(self) -> None:
        memory = StubMemoryStore([])
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                AdaptiveRAGPipeline(
                    query="q",
                    memory=memory,
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="adaptive"),
                )

    async def test_rejects_zero_top_k(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["SIMPLE"])
        with pytest.raises(ValueError, match="top_k must be a positive int"):
            with Tapestry():
                AdaptiveRAGPipeline(
                    query="q",
                    memory=memory,
                    llm=llm,
                    top_k=0,
                    _config=KnotConfig(id="adaptive"),
                )


@pytest.mark.asyncio
class TestAdaptiveRAGPipelineSimple:
    async def test_routes_simple_to_direct_llm(self) -> None:
        memory = StubMemoryStore([{"text": "irrelevant"}])
        llm = StubLLMProvider(["SIMPLE", "direct answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="What color is the sky?",
                memory=memory,
                llm=llm,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "direct answer"
        assert memory.search_queries == []


@pytest.mark.asyncio
class TestAdaptiveRAGPipelineModerate:
    async def test_routes_moderate_to_naive_rag(self) -> None:
        memory = StubMemoryStore([{"text": "some context"}])
        llm = StubLLMProvider(["MODERATE", "rag answer"])
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="Tell me about photosynthesis",
                memory=memory,
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "rag answer"
        assert len(memory.search_queries) == 1


@pytest.mark.asyncio
class TestAdaptiveRAGPipelineComplex:
    async def test_routes_complex_to_multi_hop(self) -> None:
        memory = StubMemoryStore([{"text": "hop context"}])
        llm = StubLLMProvider(
            ["COMPLEX", "sub-q1\nsub-q2\nsub-q3", "multi-hop answer"]
        )
        with Tapestry() as t:
            AdaptiveRAGPipeline(
                query="Complex multi-part question",
                memory=memory,
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="adaptive"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["adaptive"]
        assert isinstance(response, AgentResponse)
        assert response.content == "multi-hop answer"
        assert len(memory.search_queries) == 3
