"""Tests for :class:`SpeculativeRagPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.speculative_rag_pipeline import SpeculativeRagPipeline
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class TestSpeculativeRagPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_drafts_retrieves_and_verifies(self) -> None:
        memory = StubMemoryStore([{"id": "1", "text": "grounding fact"}])
        # First LLM call = draft, second = verification.
        llm = StubLLMProvider(["speculative draft", "verified final answer"])
        with Tapestry() as t:
            SpeculativeRagPipeline(
                query="what is the fact?",
                memory=memory,
                llm=llm,
                top_k=3,
                _config=KnotConfig(id="spec"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["spec"]
        assert isinstance(response, AgentResponse)
        assert response.content == "verified final answer"
        # The verification prompt should carry both the draft and the evidence.
        verify_prompt = llm.calls[-1][-1]["content"]
        assert "speculative draft" in verify_prompt
        assert "grounding fact" in verify_prompt

    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["a", "b"])
        knot = SpeculativeRagPipeline(
            query="q",
            memory=StubMemoryStore([]),
            llm=llm,
            _config=KnotConfig(id="spec"),
        )
        with self.assertRaisesRegex(TypeError, "memory must be a MemoryStore"):
            await knot.process(query="q", memory="nope", llm=llm)  # type: ignore[arg-type]
