"""Tests for :class:`NaiveRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.naive_rag_pipeline import (
    NaiveRAGPipeline,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestNaiveRAGPipelineInputContract(unittest.IsolatedAsyncioTestCase):
    """Bad inputs are refused by the framework, not by hand-written re-guards.

    These previously called ``process()`` directly, which skips the engine and
    so skips ``validate_io`` — they could only ever have passed against a guard
    inside the body. They now assert the contract at the point it is actually
    enforced: eagerly at construction for a constant (PIR-734).
    """

    def test_rejects_a_memory_that_is_not_a_store(self) -> None:
        with self.assertRaises(TypeError) as caught:
            NaiveRAGPipeline(
                query="q",
                memory="not-a-store",  # type: ignore[arg-type]
                llm=StubLLMProvider(["answer"]),
                _config=KnotConfig(id="rag"),
            )
        assert "failed validation" in str(caught.exception)

    def test_rejects_an_llm_that_is_not_a_provider(self) -> None:
        with self.assertRaises(TypeError):
            NaiveRAGPipeline(
                query="q",
                memory=StubMemoryStore([]),
                llm="not-a-provider",  # type: ignore[arg-type]
                _config=KnotConfig(id="rag"),
            )

    def test_rejects_zero_top_k(self) -> None:
        """`top_k`'s domain rides on PositiveInt, so it is still refused."""
        with self.assertRaises(TypeError) as caught:
            NaiveRAGPipeline(
                query="q",
                memory=StubMemoryStore([{"id": 1}]),
                llm=StubLLMProvider(["answer"]),
                top_k=0,
                _config=KnotConfig(id="rag"),
            )
        assert "failed validation" in str(caught.exception)

    def test_rejects_negative_top_k(self) -> None:
        with self.assertRaises(TypeError):
            NaiveRAGPipeline(
                query="q",
                memory=StubMemoryStore([]),
                llm=StubLLMProvider(["answer"]),
                top_k=-3,
                _config=KnotConfig(id="rag"),
            )


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
