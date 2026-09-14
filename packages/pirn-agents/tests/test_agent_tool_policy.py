"""Tests for :class:`pirn_agents.agent.agent_tool_policy.AgentToolPolicy` (PIR-872)."""

from __future__ import annotations

import dataclasses
import unittest

from pirn.core.run_nesting import RunNesting

from pirn_agents.agent.agent_tool_policy import AgentToolPolicy
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter


class TestAgentToolPolicy(unittest.TestCase):
    def test_carries_no_nesting_state(self) -> None:
        """Depth, path and caps are core's RunNesting; the policy holds only meter/provider."""
        self.assertFalse(issubclass(AgentToolPolicy, RunNesting))
        self.assertEqual(
            {field.name for field in dataclasses.fields(AgentToolPolicy)}, {"meter", "provider"}
        )

    def test_nothing_is_bound_at_the_root(self) -> None:
        self.assertIsNone(AgentToolPolicy.bound())
        self.assertEqual(AgentToolPolicy.current(), AgentToolPolicy())

    def test_bind_sets_and_restores(self) -> None:
        policy = AgentToolPolicy(meter=RunBudgetMeter(RunBudget(max_iterations=2)))

        with AgentToolPolicy.bind(policy):
            self.assertIs(AgentToolPolicy.bound(), policy)
            self.assertIs(AgentToolPolicy.current(), policy)

        self.assertIsNone(AgentToolPolicy.bound())

    def test_bind_restores_the_outer_policy_when_nested(self) -> None:
        outer, inner = AgentToolPolicy(), AgentToolPolicy()

        with AgentToolPolicy.bind(outer):
            with AgentToolPolicy.bind(inner):
                self.assertIs(AgentToolPolicy.bound(), inner)
            self.assertIs(AgentToolPolicy.bound(), outer)

    def test_bind_restores_even_on_exception(self) -> None:
        with self.assertRaises(ValueError):
            with AgentToolPolicy.bind(AgentToolPolicy()):
                raise ValueError("boom")

        self.assertIsNone(AgentToolPolicy.bound())
