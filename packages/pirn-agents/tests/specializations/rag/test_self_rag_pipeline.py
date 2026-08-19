"""Tests for :class:`SelfRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.self_rag_pipeline import (
    SelfRAGPipeline,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestSelfRAGPipelineProcess(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_memory_store(self) -> None:
        with self.assertRaises(TypeError):
            SelfRAGPipeline(
                query="q",
                memory="not-a-store",  # type: ignore[arg-type]
                llm=StubLLMProvider(["draft", "NO"]),
                _config=KnotConfig(id="self_rag"),
            )

    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaises(TypeError):
            SelfRAGPipeline(
                query="q",
                memory=StubMemoryStore([]),
                llm="not-llm",  # type: ignore[arg-type]
                _config=KnotConfig(id="self_rag"),
            )

    def test_rejects_zero_top_k(self) -> None:
        """`top_k`'s domain rides on PositiveInt, so it is still refused."""
        with self.assertRaises(TypeError):
            SelfRAGPipeline(
                query="q",
                memory=StubMemoryStore([]),
                llm=StubLLMProvider(["draft", "NO"]),
                top_k=0,
                _config=KnotConfig(id="self_rag"),
            )

    def test_rejects_non_string_query(self) -> None:
        with self.assertRaises(TypeError):
            SelfRAGPipeline(
                query=123,  # type: ignore[arg-type]
                memory=StubMemoryStore([]),
                llm=StubLLMProvider(["draft", "NO"]),
                _config=KnotConfig(id="self_rag"),
            )


class TestSelfRAGPipelineNoRetrieval(unittest.IsolatedAsyncioTestCase):
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


class TestSelfRAGPipelineWithRetrieval(unittest.IsolatedAsyncioTestCase):
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
