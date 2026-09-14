"""Tests for :mod:`pirn_agents.agent.agent_tool_context` — a nesting frame plus policy (ADR WS1)."""

from __future__ import annotations

import unittest

from pirn.core.run_nesting import RunNesting
from pirn.exceptions.nested_run_cycle_error import NestedRunCycleError
from pirn.exceptions.nesting_depth_exceeded_error import NestingDepthExceededError

from pirn_agents.agent.agent_tool_context import AgentToolContext


class TestAgentToolContextIsANestingFrame(unittest.TestCase):
    def test_it_is_a_run_nesting_frame(self) -> None:
        self.assertTrue(issubclass(AgentToolContext, RunNesting))
        root = AgentToolContext()
        self.assertEqual(root.depth, 0)
        self.assertEqual(root.path, ())
        self.assertIsNone(root.meter)
        self.assertIsNone(root.provider)

    def test_child_increments_depth_and_extends_the_path(self) -> None:
        root = AgentToolContext(max_depth=4)

        child = root.child("a")

        self.assertEqual(child.depth, 1)
        self.assertEqual(child.path, ("a",))
        self.assertEqual(child.stack, ("a",))
        self.assertEqual(child.max_depth, 4)

    def test_child_inherits_meter_and_provider(self) -> None:
        provider = object()
        root = AgentToolContext(max_depth=4, provider=provider)  # type: ignore[arg-type]

        child = root.child("a").child("b")

        self.assertIs(child.provider, provider)

    def test_child_raises_cores_cycle_error_when_guarded(self) -> None:
        ctx = AgentToolContext(depth=1, path=("a",), max_depth=8)

        with self.assertRaises(NestedRunCycleError):
            ctx.child("a")

    def test_child_raises_cores_depth_error_over_the_cap(self) -> None:
        ctx = AgentToolContext(depth=2, path=("a", "b"), max_depth=2)

        with self.assertRaises(NestingDepthExceededError):
            ctx.child("c")

    def test_from_current_frame_snapshots_the_running_frame(self) -> None:
        ctx = AgentToolContext.from_current_frame(provider=None)
        self.assertEqual(ctx.depth, RunNesting.current().depth)


class TestBindContext(unittest.TestCase):
    def test_root_context_is_none(self) -> None:
        self.assertIsNone(AgentToolContext.bound())

    def test_bind_sets_and_restores(self) -> None:
        ctx = AgentToolContext(depth=1, path=("a",))

        with AgentToolContext.bind(ctx):
            self.assertIs(AgentToolContext.bound(), ctx)

        self.assertIsNone(AgentToolContext.bound())

    def test_bind_restores_even_on_exception(self) -> None:
        ctx = AgentToolContext(depth=1, path=("a",))

        with self.assertRaises(ValueError):
            with AgentToolContext.bind(ctx):
                raise ValueError("boom")

        self.assertIsNone(AgentToolContext.bound())
