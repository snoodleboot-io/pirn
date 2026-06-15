"""Tests for :class:`MultiHopRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.rag.multi_hop_rag_pipeline import (
    MultiHopRAGPipeline,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestMultiHopRAGPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
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


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_query(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["sub1", "answer"])
        with Tapestry():
            k = MultiHopRAGPipeline.__new__(MultiHopRAGPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, AttributeError)):
            await k.process(query=42, memory=memory, llm=llm, top_k=5, num_hops=3)  # type: ignore[arg-type]
