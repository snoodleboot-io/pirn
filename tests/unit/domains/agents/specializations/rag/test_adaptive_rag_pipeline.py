"""Tests for :class:`AdaptiveRAGPipeline`."""

from __future__ import annotations

import unittest

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


class TestAdaptiveRAGPipelineSimple(unittest.IsolatedAsyncioTestCase):
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


class TestAdaptiveRAGPipelineModerate(unittest.IsolatedAsyncioTestCase):
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


class TestAdaptiveRAGPipelineComplex(unittest.IsolatedAsyncioTestCase):
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


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_query(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["SIMPLE", "answer"])
        with Tapestry():
            k = AdaptiveRAGPipeline.__new__(AdaptiveRAGPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, AttributeError)):
            await k.process(query=123, memory=memory, llm=llm, top_k=5)  # type: ignore[arg-type]
