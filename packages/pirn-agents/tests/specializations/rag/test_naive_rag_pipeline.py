"""Tests for :class:`NaiveRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.naive_rag_pipeline import (
    NaiveRAGPipeline,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestNaiveRAGPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["answer"])
        memory = StubMemoryStore([])
        knot = NaiveRAGPipeline(
            query="q",
            memory=memory,
            llm=llm,
            _config=KnotConfig(id="rag"),
        )
        with self.assertRaisesRegex(TypeError, "memory must be a MemoryStore"):
            await knot.process(
                query="q",
                memory="not-a-store",  # type: ignore[arg-type]
                llm=llm,
            )

    async def test_rejects_zero_top_k(self) -> None:
        memory = StubMemoryStore([{"id": 1}])
        llm = StubLLMProvider(["answer"])
        knot = NaiveRAGPipeline(
            query="q",
            memory=memory,
            llm=llm,
            _config=KnotConfig(id="rag"),
        )
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await knot.process(query="q", memory=memory, llm=llm, top_k=0)


class TestNaiveRAGPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_response_with_retrieved_context(self) -> None:
        memory = StubMemoryStore(
            [
                {"id": 1, "text": "qubits are stable"},
                {"id": 2, "text": "ibm announced 1000 qubit"},
            ]
        )
        llm = StubLLMProvider(["The answer is 42."])
        with Tapestry() as t:
            NaiveRAGPipeline(
                query="quantum computing facts",
                memory=memory,
                llm=llm,
                top_k=2,
                _config=KnotConfig(id="rag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["rag"]
        assert isinstance(response, AgentResponse)
        assert response.content == "The answer is 42."
        assert response.finish_reason == "stop"
        assert memory.search_queries == ["quantum computing facts"]
        # Prompt should have been forwarded to the LLM with retrieved context.
        assert len(llm.calls) == 1
        prompt_messages = llm.calls[0]
        prompt_body = prompt_messages[-1]["content"]
        assert "qubits are stable" in prompt_body
        assert "quantum computing facts" in prompt_body
