"""Tests for :class:`SubQuestionRagPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.sub_question_rag_pipeline import SubQuestionRagPipeline
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class TestSubQuestionRagPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_decomposes_retrieves_and_synthesizes(self) -> None:
        memory = StubMemoryStore([{"id": "1", "text": "fact"}])
        llm = StubLLMProvider(["sub one\nsub two", "combined answer"])
        with Tapestry() as t:
            SubQuestionRagPipeline(
                query="compound question",
                memory=memory,
                llm=llm,
                max_sub_questions=3,
                top_k=2,
                _config=KnotConfig(id="subq"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["subq"]
        assert isinstance(response, AgentResponse)
        assert response.content == "combined answer"
        assert sorted(memory.search_queries) == ["sub one", "sub two"]

    def test_rejects_non_llm(self) -> None:
        with self.assertRaises(TypeError):
            SubQuestionRagPipeline(
                query="q",
                memory=StubMemoryStore([]),
                llm="nope",  # type: ignore[arg-type]
                _config=KnotConfig(id="subq"),
            )
