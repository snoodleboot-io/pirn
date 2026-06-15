"""Tests for :class:`ResearchAgent`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.specialized_agents.research_agent import (
    ResearchAgent,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


class TestResearchAgentProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_tool(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        tool = StubTool(name="search")
        agent = ResearchAgent(
            topic="quantum",
            llm=llm,
            search_tool=tool,
            _config=KnotConfig(id="research"),
        )
        with self.assertRaisesRegex(TypeError, "search_tool must be a Tool"):
            await agent.process(topic="quantum", llm=llm, search_tool="not-a-tool")  # type: ignore[arg-type]

    async def test_rejects_zero_max_searches(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        tool = StubTool(name="search")
        agent = ResearchAgent(
            topic="quantum",
            llm=llm,
            search_tool=tool,
            _config=KnotConfig(id="research"),
        )
        with self.assertRaisesRegex(ValueError, "max_searches"):
            await agent.process(topic="quantum", llm=llm, search_tool=tool, max_searches=0)


class TestResearchAgentHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_uses_tool_then_summarises(self) -> None:
        llm = StubLLMProvider(
            [
                "Action: search\nAction Input: quantum computing 2024",
                "Final Answer: Quantum computing reached 1000 qubits in 2024.",
            ]
        )
        tool = StubTool(
            name="search",
            handler="IBM announces 1000-qubit chip",
        )
        with Tapestry() as t:
            ResearchAgent(
                topic="quantum computing breakthroughs",
                llm=llm,
                search_tool=tool,
                max_searches=4,
                _config=KnotConfig(id="research"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["research"]
        assert isinstance(response, AgentResponse)
        assert response.finish_reason == "stop"
        assert "1000 qubits" in response.content
        assert tool.invocations == [{"input": "quantum computing 2024"}]
