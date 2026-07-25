"""Tests for :class:`FlareActiveRagPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.flare_active_rag_pipeline import FlareActiveRagPipeline
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class TestFlareActiveRagPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_retrieves_only_on_low_confidence(self) -> None:
        memory = StubMemoryStore([{"id": "1", "text": "evidence"}])
        llm = StubLLMProvider(
            [
                "CONF=0.9: High confidence sentence.",  # step 0 gen (no retrieval)
                "CONF=0.2: Low confidence claim.",  # step 1 gen (triggers retrieval)
                "Grounded corrected claim.",  # step 1 regenerate
                "DONE",  # step 2 gen -> stop
            ]
        )
        with Tapestry() as t:
            FlareActiveRagPipeline(
                query="explain X",
                memory=memory,
                llm=llm,
                confidence_threshold=0.5,
                max_sentences=5,
                max_retrieval_calls=3,
                _config=KnotConfig(id="flare"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["flare"]
        assert isinstance(response, AgentResponse)
        assert response.content == "High confidence sentence. Grounded corrected claim."
        # Retrieval fired once, keyed on the low-confidence sentence.
        assert memory.search_queries == ["Low confidence claim."]

    async def test_retrieval_calls_are_bounded(self) -> None:
        memory = StubMemoryStore([{"id": "1", "text": "evidence"}])
        # Every sentence is low-confidence, but the budget caps retrieval at 1.
        llm = StubLLMProvider(
            [
                "CONF=0.1: first weak.",  # gen 0 -> retrieval 1
                "rewritten one.",  # regenerate 0
                "CONF=0.1: second weak.",  # gen 1 -> budget exhausted, no retrieval
                "DONE",  # gen 2 -> stop
            ]
        )
        with Tapestry() as t:
            FlareActiveRagPipeline(
                query="q",
                memory=memory,
                llm=llm,
                confidence_threshold=0.5,
                max_sentences=5,
                max_retrieval_calls=1,
                _config=KnotConfig(id="flare"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert len(memory.search_queries) == 1
        response = result.outputs["flare"]
        assert isinstance(response, AgentResponse)
        assert response.content == "rewritten one. second weak."

    async def test_rejects_non_positive_budget(self) -> None:
        knot = FlareActiveRagPipeline(
            query="q",
            memory=StubMemoryStore([]),
            llm=StubLLMProvider(["DONE"]),
            _config=KnotConfig(id="flare"),
        )
        with self.assertRaisesRegex(ValueError, "max_retrieval_calls must be a positive int"):
            await knot.process(
                query="q",
                memory=StubMemoryStore([]),
                llm=StubLLMProvider(["DONE"]),
                max_retrieval_calls=0,
            )
