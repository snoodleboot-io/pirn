"""Tests for an agent's declaration — ``AgentTool.declaration()``."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.tools.agent_tool import AgentTool
from tests.agent_tool_doubles import NoInputAgent, TopicMaxAgent, reset_doubles


class TestAgentDeclaration(unittest.TestCase):
    def setUp(self) -> None:
        reset_doubles()

    def test_derives_declared_inputs_with_the_agents_own_values_as_defaults(self) -> None:
        with Tapestry():
            agent = TopicMaxAgent(topic="seed", _config=KnotConfig(id="a"))

        schema = dict(AgentTool(agent).declaration().parameters)

        self.assertEqual(schema["type"], "object")
        self.assertEqual(
            schema["properties"],
            {
                "topic": {"type": "string", "default": "seed"},
                "max_results": {"type": "integer", "default": 5},
            },
        )
        # Both are supplied by the wrapped agent, so a call may omit either.
        self.assertNotIn("required", schema)

    def test_filters_out_dependency_parameters(self) -> None:
        with Tapestry():
            agent = TopicMaxAgent(topic="seed", _config=KnotConfig(id="a"))

        schema = dict(AgentTool(agent).declaration().parameters)

        self.assertNotIn("llm", schema["properties"])
        self.assertNotIn("tools", schema["properties"])

    def test_falls_back_to_task_default_when_no_inputs(self) -> None:
        with Tapestry():
            agent = NoInputAgent(_config=KnotConfig(id="a"))

        schema = dict(AgentTool(agent).declaration().parameters)

        self.assertEqual(schema, AgentTool.default_schema())
        self.assertEqual(schema["properties"], {"task": {"type": "string"}})
