"""Tests for :mod:`pirn_agents.agent_tool_context` (F7-S3 state)."""

from __future__ import annotations

import unittest

from pirn_agents.agent_tool_context import (
    AgentToolContext,
    bind_agent_tool_context,
    current_agent_tool_context,
)
from pirn_agents.exceptions.agent_cycle_error import AgentCycleError
from pirn_agents.exceptions.agent_depth_exceeded_error import (
    AgentDepthExceededError,
)


class TestAgentToolContextChild(unittest.TestCase):
    def test_child_increments_depth_and_extends_stack(self) -> None:
        root = AgentToolContext(max_depth=4)

        child = root.child("a")

        self.assertEqual(child.depth, 1)
        self.assertEqual(child.stack, ("a",))
        self.assertEqual(child.max_depth, 4)

    def test_child_inherits_meter_and_provider(self) -> None:
        provider = object()
        root = AgentToolContext(max_depth=4, provider=provider)  # type: ignore[arg-type]

        child = root.child("a").child("b")

        self.assertIs(child.provider, provider)

    def test_child_raises_cycle_when_key_already_active(self) -> None:
        ctx = AgentToolContext(depth=1, stack=("a",), max_depth=8)

        with self.assertRaises(AgentCycleError):
            ctx.child("a")

    def test_child_raises_depth_when_over_cap(self) -> None:
        ctx = AgentToolContext(depth=2, stack=("a", "b"), max_depth=2)

        with self.assertRaises(AgentDepthExceededError):
            ctx.child("c")


class TestBindContext(unittest.TestCase):
    def test_root_context_is_none(self) -> None:
        self.assertIsNone(current_agent_tool_context())

    def test_bind_sets_and_restores(self) -> None:
        ctx = AgentToolContext(depth=1, stack=("a",))

        with bind_agent_tool_context(ctx):
            self.assertIs(current_agent_tool_context(), ctx)

        self.assertIsNone(current_agent_tool_context())

    def test_bind_restores_even_on_exception(self) -> None:
        ctx = AgentToolContext(depth=1, stack=("a",))

        with self.assertRaises(ValueError):
            with bind_agent_tool_context(ctx):
                raise ValueError("boom")

        self.assertIsNone(current_agent_tool_context())
