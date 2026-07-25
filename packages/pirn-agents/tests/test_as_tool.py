"""Tests for the ``as_tool`` API and mixin (F7-S2)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent_tool import AgentTool
from pirn_agents.as_tool import as_tool
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse
from tests.agent_tool_doubles import AGENT_CALLS, StubAgent, reset_doubles
from tests.conftest import StubLLMProvider


class TestAsToolFunction(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_free_function_returns_agent_tool(self) -> None:
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="a"))

        tool = as_tool(agent, name="helper", description="a helper")

        self.assertIsInstance(tool, AgentTool)
        self.assertEqual(tool.name, "helper")
        self.assertEqual(tool.description, "a helper")

    async def test_mixin_method_matches_free_function(self) -> None:
        with Tapestry():
            agent = StubAgent(reply="did", _config=KnotConfig(id="a"))

        tool = agent.as_tool(name="helper")
        result = await tool.invoke({"topic": "thing"})

        self.assertIsInstance(tool, AgentTool)
        self.assertEqual(result.result.content, "did:thing")


class TestAsToolInReActLoop(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_agent_tool_works_inside_react_loop_no_adapter(self) -> None:
        # Outer loop: act via the wrapped agent, then finish.
        outer_llm = StubLLMProvider(
            [
                "Action: helper\nAction Input: investigate",
                "Final Answer: wrapped up",
            ]
        )
        with Tapestry():
            inner_agent = StubAgent(reply="researched", _config=KnotConfig(id="inner"))
        helper = inner_agent.as_tool(name="helper")

        with Tapestry() as tapestry:
            ReActLoop(
                messages=(AgentMessage(role="user", content="Look into it."),),
                llm=outer_llm,
                tools=(helper,),
                max_iterations=3,
                _config=KnotConfig(id="outer"),
            )
        run = await tapestry.run(RunRequest())

        self.assertTrue(run.succeeded)
        response = run.outputs["outer"]
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.content, "wrapped up")
        # The nested agent was actually invoked through the tool.
        self.assertEqual(len(AGENT_CALLS["inner"]), 1)
        self.assertEqual(AGENT_CALLS["inner"][0]["topic"], "investigate")
