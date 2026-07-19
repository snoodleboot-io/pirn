"""Tests for :mod:`pirn_agents.agent_schema_deriver` (F7-S2 schema derivation)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.agent_schema_deriver import AgentSchemaDeriver
from tests.agent_tool_doubles import NoInputAgent, TopicMaxAgent, reset_doubles


class TestDeriveAgentSchema(unittest.TestCase):
    def setUp(self) -> None:
        reset_doubles()

    def test_derives_declared_inputs_and_required(self) -> None:
        with Tapestry():
            agent = TopicMaxAgent(topic="seed", _config=KnotConfig(id="a"))

        schema = dict(AgentSchemaDeriver().derive(agent))

        self.assertEqual(schema["type"], "object")
        self.assertEqual(
            schema["properties"],
            {"topic": {"type": "string"}, "max_results": {"type": "integer"}},
        )
        # topic has no default (required); max_results has one (optional).
        self.assertEqual(schema["required"], ["topic"])

    def test_filters_out_dependency_parameters(self) -> None:
        with Tapestry():
            agent = TopicMaxAgent(topic="seed", _config=KnotConfig(id="a"))

        schema = dict(AgentSchemaDeriver().derive(agent))

        self.assertNotIn("llm", schema["properties"])
        self.assertNotIn("tools", schema["properties"])

    def test_falls_back_to_task_default_when_no_inputs(self) -> None:
        with Tapestry():
            agent = NoInputAgent(_config=KnotConfig(id="a"))

        schema = dict(AgentSchemaDeriver().derive(agent))

        self.assertEqual(schema, AgentSchemaDeriver().default_schema())
        self.assertEqual(schema["properties"], {"task": {"type": "string"}})
