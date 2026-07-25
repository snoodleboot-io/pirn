"""Handoff/swarm integration + Pattern 16 doc example (F7-S6).

Asserts that tool-style agent calls and handoff-style calls share the same
underlying :class:`~pirn_agents.agent_invoker.AgentInvoker` machinery, that a
swarm of agents-as-tools works inside a single ReAct loop, and that the rewritten
Pattern 16 example runs end-to-end (so the doc cannot silently drift).
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent_invoker import AgentInvoker
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.specializations.specialized_agents.research_agent import (
    ResearchAgent,
)
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse
from tests.agent_tool_doubles import AGENT_CALLS, StubAgent, reset_doubles
from tests.conftest import StubLLMProvider, StubTool


class TestSharedMachinery(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_tool_style_and_handoff_style_agree(self) -> None:
        # Tool-style: dispatch via AgentTool.invoke.
        with Tapestry():
            agent = StubAgent(reply="answer", _config=KnotConfig(id="agent"))
        tool = agent.as_tool()
        tool_style = await tool.invoke({"topic": "same"})

        # Handoff-style: the same shared runner a transfer/swarm path would use.
        handoff_style = await AgentInvoker().invoke(
            agent,
            {"topic": "same"},
            name=tool.name,
            schema=tool.parameters_schema,
        )

        self.assertEqual(tool_style.result.content, handoff_style.result.content)
        self.assertEqual(tool_style.result.content, "answer:same")

    async def test_swarm_of_agent_tools_in_react_loop(self) -> None:
        outer_llm = StubLLMProvider(
            [
                "Action: beta\nAction Input: route here",
                "Final Answer: done",
            ]
        )
        with Tapestry():
            alpha = StubAgent(reply="A", _config=KnotConfig(id="alpha"))
            beta = StubAgent(reply="B", _config=KnotConfig(id="beta"))

        with Tapestry() as tapestry:
            ReActLoop(
                messages=(AgentMessage(role="user", content="pick one"),),
                llm=outer_llm,
                tools=(alpha.as_tool(name="alpha"), beta.as_tool(name="beta")),
                max_iterations=3,
                _config=KnotConfig(id="swarm"),
            )
        run = await tapestry.run(RunRequest())

        self.assertTrue(run.succeeded)
        # The planner handed off to beta, not alpha.
        self.assertIn("beta", AGENT_CALLS)
        self.assertNotIn("alpha", AGENT_CALLS)


class TestPattern16DocExample(unittest.IsolatedAsyncioTestCase):
    async def test_research_agent_as_tool_in_react_loop(self) -> None:
        # Mirrors the rewritten Pattern 16: a ResearchAgent exposed via as_tool()
        # and driven by an outer ReAct loop.
        outer_llm = StubLLMProvider(
            [
                "Action: research\nAction Input: CRISPR advances",
                "Final Answer: summarised",
            ]
        )
        research_llm = StubLLMProvider(["Final Answer: found CRISPR facts"])
        search_tool = StubTool(name="search", handler="search hit")

        with Tapestry():
            researcher = ResearchAgent(
                topic="seed",
                llm=research_llm,
                search_tool=search_tool,
                max_searches=2,
                _config=KnotConfig(id="researcher"),
            )
        research_tool = researcher.as_tool(name="research")

        with Tapestry() as tapestry:
            ReActLoop(
                messages=(AgentMessage(role="user", content="Research CRISPR advances."),),
                llm=outer_llm,
                tools=(research_tool,),
                max_iterations=3,
                _config=KnotConfig(id="outer"),
            )
        run = await tapestry.run(RunRequest())

        self.assertTrue(run.succeeded)
        response = run.outputs["outer"]
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.content, "summarised")
