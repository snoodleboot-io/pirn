"""Tests for :class:`pirn_agents.tools.agent_tool.AgentTool` — an agent as a capability (ADR WS1)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.tools.agent_tool import AgentTool
from pirn_agents.tools.agent_tool_call import AgentToolCall
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.agent_tool_doubles import AGENT_CALLS, StubAgent, reset_doubles


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

    def test_is_a_tool_capability(self) -> None:
        tool = AgentTool(self._agent())
        self.assertIsInstance(tool, ToolFactory)
        self.assertIs(tool.knot_class, AgentToolCall)
        self.assertIs(ToolFactory.of(tool), tool)

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

    def test_declaration_hides_collaborators_and_shows_bound_inputs_as_defaults(self) -> None:
        tool = AgentTool(self._agent(reply="hi"))
        properties = tool.declaration().parameters["properties"]
        self.assertNotIn("llm", properties)
        self.assertEqual(properties["reply"]["default"], "hi")
        self.assertIn("topic", properties)

    def test_clear_credentials_drops_provider(self) -> None:
        tool = AgentTool(self._agent(), provider=object())  # type: ignore[arg-type]

        tool._clear_credentials()

        self.assertIsNone(tool._provider)


class TestAgentToolAsAKnot(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    def _tool(self, **kwargs: object) -> AgentTool:
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"), **kwargs)
        return AgentTool(agent)

    async def test_one_call_runs_the_agent_as_a_nested_pipeline(self) -> None:
        tool = self._tool(reply="done", usage={"input_tokens": 2, "output_tokens": 3})
        with Tapestry() as t:
            tool.for_call(
                ToolCall(tool_name="stub_agent", arguments={"topic": "quantum"}, call_id="c1")
            )
        result = await t.run(RunRequest())

        assert result.succeeded, result.exceptions
        response = result.outputs["c1"]
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.data, "done:quantum")
        # The agent itself ran under its own id in the call's inner run.
        children = await t.history.children_of(result.run_id)
        inner_ids = {row.knot_id for child in children for row in child.lineage}
        self.assertIn("agent", inner_ids)
        self.assertEqual(AGENT_CALLS["agent"][0]["topic"], "quantum")

    async def test_react_style_input_aliases_to_primary_param(self) -> None:
        tool = self._tool(reply="did")

        view = await tool.run_view({"input": "search this"})

        self.assertEqual(view.result.data, "did:search this")

    async def test_the_view_carries_tokens_from_the_response_usage(self) -> None:
        tool = self._tool(reply="done", usage={"input_tokens": 2, "output_tokens": 3})

        view = await tool.run_view({"topic": "quantum"})

        self.assertEqual(view.status, "ok")
        self.assertEqual(view.tokens, 5)

    async def test_call_id_taken_from_arguments(self) -> None:
        tool = self._tool()

        view = await tool.run_view({"topic": "x", "call_id": "abc-123"})

        self.assertEqual(view.call_id, "abc-123")

    async def test_inner_error_surfaces_as_the_calls_err(self) -> None:
        tool = self._tool(fail=True)
        with Tapestry() as t:
            tool.for_call(
                ToolCall(tool_name="stub_agent", arguments={"topic": "boom"}, call_id="c1")
            )
        result = await t.run(RunRequest())

        self.assertFalse(result.succeeded)
        self.assertEqual([rec.knot_id for rec in result.exceptions], ["c1"])

    async def test_inner_error_is_an_error_view_outside_the_engine(self) -> None:
        tool = self._tool(fail=True)

        view = await tool.run_view({"topic": "boom"})

        self.assertEqual(view.status, "error")
        self.assertIsNone(view.result)
        self.assertIsNotNone(view.error)
        self.assertIn("boom", view.error or "")
