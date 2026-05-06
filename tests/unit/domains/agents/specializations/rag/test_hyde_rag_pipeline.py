"""Tests for :class:`HyDERAGPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.hyde_rag_pipeline import (
    HyDERAGPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestHyDERAGPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_two_llm_calls_and_search_uses_hypothesis(self) -> None:
        memory = StubMemoryStore([{"id": 1, "text": "earth orbits the sun"}])
        llm = StubLLMProvider(
            [
                "the moon is made of cheese",  # hypothesis
                "Final answer based on docs",  # actual answer
            ]
        )
        with Tapestry() as t:
            HyDERAGPipeline(
                query="what orbits the sun?",
                memory=memory,
                llm=llm,
                top_k=1,
                _config=KnotConfig(id="hyde"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["hyde"]
        assert isinstance(response, AgentResponse)
        assert response.content == "Final answer based on docs"
        # Two LLM calls: hypothesis + final.
        assert len(llm.calls) == 2
        # The retrieval query must be the hypothesis text, not the original.
        assert memory.search_queries == ["the moon is made of cheese"]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_query(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["hypothesis", "answer"])
        with Tapestry():
            k = HyDERAGPipeline.__new__(HyDERAGPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, AttributeError)):
            await k.process(query=99, memory=memory, llm=llm, top_k=5)  # type: ignore[arg-type]
