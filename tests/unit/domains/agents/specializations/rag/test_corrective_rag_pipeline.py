"""Tests for :class:`CorrectiveRAGPipeline`."""

from __future__ import annotations

import unittest

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


class TestCorrectiveRAGPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
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


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_query(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["answer"])
        tool = StubTool(name="web", handler="fallback")
        with Tapestry():
            k = CorrectiveRAGPipeline.__new__(CorrectiveRAGPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, AttributeError)):
            await k.process(
                query=42,  # type: ignore[arg-type]
                memory=memory,
                llm=llm,
                fallback_tool=tool,
                top_k=5,
                relevance_threshold=0.5,
            )
