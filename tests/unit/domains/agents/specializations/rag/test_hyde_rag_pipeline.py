"""Tests for :class:`HyDERAGPipeline`."""

from __future__ import annotations

import pytest

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


@pytest.mark.asyncio
class TestHyDERAGPipelineConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        memory = StubMemoryStore([{"id": 1}])
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                HyDERAGPipeline(
                    query="q",
                    memory=memory,
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="hyde"),
                )

    async def test_rejects_negative_top_k(self) -> None:
        memory = StubMemoryStore([{"id": 1}])
        llm = StubLLMProvider(["x"])
        with pytest.raises(ValueError, match="top_k must be a positive int"):
            with Tapestry():
                HyDERAGPipeline(
                    query="q",
                    memory=memory,
                    llm=llm,
                    top_k=-1,
                    _config=KnotConfig(id="hyde"),
                )


@pytest.mark.asyncio
class TestHyDERAGPipelineHappyPath:
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
