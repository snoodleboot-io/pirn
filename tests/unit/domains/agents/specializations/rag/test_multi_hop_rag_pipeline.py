"""Tests for :class:`MultiHopRAGPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.multi_hop_rag_pipeline import (
    MultiHopRAGPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


@pytest.mark.asyncio
class TestMultiHopRAGPipelineConstruction:
    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["sub1\nsub2\nsub3", "answer"])
        with pytest.raises(TypeError, match="memory must be a MemoryStore"):
            with Tapestry():
                MultiHopRAGPipeline(
                    query="q",
                    memory="bad",  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="mhop"),
                )

    async def test_rejects_zero_top_k(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["sub1\nsub2\nsub3", "answer"])
        with pytest.raises(ValueError, match="top_k must be a positive int"):
            with Tapestry():
                MultiHopRAGPipeline(
                    query="q",
                    memory=memory,
                    llm=llm,
                    top_k=0,
                    _config=KnotConfig(id="mhop"),
                )

    async def test_rejects_zero_num_hops(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["sub1", "answer"])
        with pytest.raises(ValueError, match="num_hops must be a positive int"):
            with Tapestry():
                MultiHopRAGPipeline(
                    query="q",
                    memory=memory,
                    llm=llm,
                    num_hops=0,
                    _config=KnotConfig(id="mhop"),
                )


@pytest.mark.asyncio
class TestMultiHopRAGPipelineHappyPath:
    async def test_decomposes_retrieves_per_hop_and_synthesizes(self) -> None:
        memory = StubMemoryStore([{"text": "context fact"}])
        llm = StubLLMProvider(["sub-q1\nsub-q2\nsub-q3", "final synthesized answer"])
        with Tapestry() as t:
            MultiHopRAGPipeline(
                query="Why did X cause Y via Z?",
                memory=memory,
                llm=llm,
                top_k=1,
                num_hops=3,
                _config=KnotConfig(id="mhop"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["mhop"]
        assert isinstance(response, AgentResponse)
        assert response.content == "final synthesized answer"
        assert len(memory.search_queries) == 3
        assert memory.search_queries[0] == "sub-q1"
        assert memory.search_queries[1] == "sub-q2"
        assert memory.search_queries[2] == "sub-q3"

    async def test_uses_original_query_when_decompose_is_empty(self) -> None:
        memory = StubMemoryStore([{"text": "ctx"}])
        llm = StubLLMProvider(["", "fallback answer"])
        with Tapestry() as t:
            MultiHopRAGPipeline(
                query="simple question",
                memory=memory,
                llm=llm,
                num_hops=2,
                _config=KnotConfig(id="mhop"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["mhop"]
        assert isinstance(response, AgentResponse)
        assert response.content == "fallback answer"
        assert memory.search_queries == ["simple question"]
