"""Tests for :class:`SelfRAGPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.self_rag_pipeline import (
    SelfRAGPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


@pytest.mark.asyncio
class TestSelfRAGPipelineConstruction:
    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["draft", "NO"])
        with pytest.raises(TypeError, match="memory must be a MemoryStore"):
            with Tapestry():
                SelfRAGPipeline(
                    query="q",
                    memory="not-a-store",  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="self_rag"),
                )

    async def test_rejects_non_llm_provider(self) -> None:
        memory = StubMemoryStore([])
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                SelfRAGPipeline(
                    query="q",
                    memory=memory,
                    llm="not-llm",  # type: ignore[arg-type]
                    _config=KnotConfig(id="self_rag"),
                )

    async def test_rejects_zero_top_k(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["draft", "NO"])
        with pytest.raises(ValueError, match="top_k must be a positive int"):
            with Tapestry():
                SelfRAGPipeline(
                    query="q",
                    memory=memory,
                    llm=llm,
                    top_k=0,
                    _config=KnotConfig(id="self_rag"),
                )


@pytest.mark.asyncio
class TestSelfRAGPipelineNoRetrieval:
    async def test_returns_draft_when_retrieval_not_needed(self) -> None:
        memory = StubMemoryStore([{"text": "context"}])
        llm = StubLLMProvider(["I know the answer already.", "NO"])
        with Tapestry() as t:
            SelfRAGPipeline(
                query="What is 2+2?",
                memory=memory,
                llm=llm,
                _config=KnotConfig(id="self_rag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["self_rag"]
        assert isinstance(response, AgentResponse)
        assert response.content == "I know the answer already."
        assert response.finish_reason == "stop"
        assert memory.search_queries == []


@pytest.mark.asyncio
class TestSelfRAGPipelineWithRetrieval:
    async def test_retrieves_and_regenerates_when_needed(self) -> None:
        memory = StubMemoryStore([{"text": "retrieved fact"}])
        llm = StubLLMProvider(["draft answer", "YES", "final answer with context"])
        with Tapestry() as t:
            SelfRAGPipeline(
                query="complex question",
                memory=memory,
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="self_rag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["self_rag"]
        assert isinstance(response, AgentResponse)
        assert response.content == "final answer with context"
        assert memory.search_queries == ["complex question"]

    async def test_rejects_non_string_query_at_construction(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["draft", "NO"])
        with pytest.raises(TypeError, match="query"):
            with Tapestry():
                SelfRAGPipeline(
                    query=123,  # type: ignore[arg-type]
                    memory=memory,
                    llm=llm,
                    _config=KnotConfig(id="self_rag"),
                )
