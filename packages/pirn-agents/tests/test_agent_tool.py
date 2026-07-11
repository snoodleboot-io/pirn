"""Tests for :class:`pirn_agents.agent_tool.AgentTool` (F7-S1)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.agent_tool import AgentTool
from pirn_agents.tool import Tool
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_status import ToolStatus
from tests.agent_tool_doubles import StubAgent, reset_doubles


class TestAgentToolConstruction(unittest.TestCase):
    def setUp(self) -> None:
        reset_doubles()

    def _agent(self, **kwargs: object) -> StubAgent:
        with Tapestry():
            return StubAgent(_config=KnotConfig(id="agent"), **kwargs)

    def test_rejects_non_subtapestry(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a SubTapestry"):
            AgentTool(object())  # type: ignore[arg-type]

    def test_rejects_non_positive_max_depth(self) -> None:
        with self.assertRaisesRegex(TypeError, "max_depth must be a positive int"):
            AgentTool(self._agent(), max_depth=0)

    def test_is_a_tool(self) -> None:
        self.assertIsInstance(AgentTool(self._agent()), Tool)

    def test_defaults_name_and_description_from_agent(self) -> None:
        tool = AgentTool(self._agent())

        self.assertEqual(tool.name, "stub_agent")
        self.assertTrue(tool.description)

    def test_name_and_description_overridable(self) -> None:
        tool = AgentTool(self._agent(), name="research", description="deep research")

        self.assertEqual(tool.name, "research")
        self.assertEqual(tool.description, "deep research")

    def test_schema_overridable(self) -> None:
        schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        tool = AgentTool(self._agent(), input_schema=schema)

        self.assertEqual(dict(tool.parameters_schema), schema)

    def test_clear_credentials_drops_provider(self) -> None:
        tool = AgentTool(self._agent(), provider=object())  # type: ignore[arg-type]

        tool._clear_credentials()

        self.assertIsNone(tool._provider)


class TestAgentToolInvoke(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    def _tool(self, **kwargs: object) -> AgentTool:
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"), **kwargs)
        return AgentTool(agent)

    async def test_maps_agent_response_to_tool_result(self) -> None:
        tool = self._tool(reply="done", usage={"input_tokens": 2, "output_tokens": 3})

        result = await tool.invoke({"topic": "quantum"})

        self.assertEqual(result.status, ToolStatus.OK)
        self.assertIsInstance(result.result, AgentResponse)
        self.assertEqual(result.result.content, "done:quantum")
        self.assertEqual(result.tokens, 5)
        self.assertIsNotNone(result.latency)

    async def test_react_style_input_aliases_to_primary_param(self) -> None:
        tool = self._tool(reply="did")

        result = await tool.invoke({"input": "search this"})

        self.assertEqual(result.result.content, "did:search this")

    async def test_call_id_taken_from_arguments(self) -> None:
        tool = self._tool()

        result = await tool.invoke({"topic": "x", "call_id": "abc-123"})

        self.assertEqual(result.call_id, "abc-123")

    async def test_inner_error_surfaces_as_tool_error(self) -> None:
        tool = self._tool(fail=True)

        result = await tool.invoke({"topic": "boom"})

        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIsNone(result.result)
        self.assertIsNotNone(result.error)
        self.assertIn("boom", result.error or "")

    async def test_invoke_returns_without_raising_on_inner_failure(self) -> None:
        tool = self._tool(fail=True)

        # Must not raise — the failure is a value, not an exception.
        result = await tool.invoke({"topic": "boom"})

        self.assertEqual(result.status, ToolStatus.ERROR)
