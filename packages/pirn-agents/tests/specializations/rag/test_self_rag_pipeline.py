"""Tests for :class:`SelfRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.rag.self_rag_pipeline import (
    SelfRAGPipeline,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestSelfRAGPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["draft", "NO"])
        memory = StubMemoryStore([])
        knot = SelfRAGPipeline(
            query="q",
            memory=memory,
            llm=llm,
            _config=KnotConfig(id="self_rag"),
        )
        with self.assertRaisesRegex(TypeError, "memory must be a MemoryStore"):
            await knot.process(
                query="q",
                memory="not-a-store",  # type: ignore[arg-type]
                llm=llm,
            )

    async def test_rejects_non_llm_provider(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider([])
        knot = SelfRAGPipeline(
            query="q",
            memory=memory,
            llm=llm,
            _config=KnotConfig(id="self_rag"),
        )
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                query="q",
                memory=memory,
                llm="not-llm",  # type: ignore[arg-type]
            )

    async def test_rejects_zero_top_k(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["draft", "NO"])
        knot = SelfRAGPipeline(
            query="q",
            memory=memory,
            llm=llm,
            _config=KnotConfig(id="self_rag"),
        )
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await knot.process(query="q", memory=memory, llm=llm, top_k=0)

    async def test_rejects_non_string_query(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["draft", "NO"])
        knot = SelfRAGPipeline(
            query="q",
            memory=memory,
            llm=llm,
            _config=KnotConfig(id="self_rag"),
        )
        with self.assertRaisesRegex(TypeError, "query"):
            await knot.process(
                query=123,  # type: ignore[arg-type]
                memory=memory,
                llm=llm,
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
