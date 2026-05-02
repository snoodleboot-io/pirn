"""Tests for :class:`CorrectiveRAGPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.corrective_rag_pipeline import (
    CorrectiveRAGPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
    StubTool,
)


@pytest.mark.asyncio
class TestCorrectiveRAGPipelineConstruction:
    async def test_rejects_non_tool_fallback(self) -> None:
        memory = StubMemoryStore([{"id": 1}])
        llm = StubLLMProvider(["x"])
        with pytest.raises(
            TypeError, match="fallback_tool must be a Tool"
        ):
            with Tapestry():
                CorrectiveRAGPipeline(
                    query="q",
                    memory=memory,
                    llm=llm,
                    fallback_tool="not-a-tool",  # type: ignore[arg-type]
                    _config=KnotConfig(id="crag"),
                )

    async def test_rejects_out_of_range_threshold(self) -> None:
        memory = StubMemoryStore([{"id": 1}])
        llm = StubLLMProvider(["x"])
        tool = StubTool(name="web", handler="fallback")
        with pytest.raises(
            ValueError, match="relevance_threshold must be in"
        ):
            with Tapestry():
                CorrectiveRAGPipeline(
                    query="q",
                    memory=memory,
                    llm=llm,
                    fallback_tool=tool,
                    relevance_threshold=2.0,
                    _config=KnotConfig(id="crag"),
                )


@pytest.mark.asyncio
class TestCorrectiveRAGPipelineHappyPath:
    async def test_uses_relevant_docs_when_available(self) -> None:
        memory = StubMemoryStore(
            [{"id": 1, "text": "qubits stable"}, {"id": 2, "text": "irrelevant"}]
        )
        llm = StubLLMProvider(["from-docs"])
        tool = StubTool(name="web", handler="should-not-fire")
        with Tapestry() as t:
            CorrectiveRAGPipeline(
                query="qubits",
                memory=memory,
                llm=llm,
                fallback_tool=tool,
                top_k=2,
                relevance_threshold=0.5,
                _config=KnotConfig(id="crag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["crag"]
        assert isinstance(response, AgentResponse)
        assert response.content == "from-docs"
        assert tool.invocations == []

    async def test_falls_back_to_tool_when_no_docs_relevant(self) -> None:
        memory = StubMemoryStore(
            [{"id": 1, "text": "completely off-topic content"}]
        )
        llm = StubLLMProvider(["from-fallback"])
        tool = StubTool(name="web", handler="web search hit")
        with Tapestry() as t:
            CorrectiveRAGPipeline(
                query="elephants",
                memory=memory,
                llm=llm,
                fallback_tool=tool,
                top_k=1,
                relevance_threshold=0.5,
                _config=KnotConfig(id="crag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["crag"]
        assert isinstance(response, AgentResponse)
        assert response.content == "from-fallback"
        assert tool.invocations == [{"input": "elephants"}]
        prompt_body = llm.calls[0][-1]["content"]
        assert "fallback" in prompt_body
        assert "web search hit" in prompt_body
