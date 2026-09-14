"""Nested agent-as-tool policy: nesting guard, budget propagation, provider reuse (ADR WS1).

The depth and cycle guard is core's ``RunNesting`` applied by
:class:`~pirn_agents.tools.agent_tool_call.AgentToolCall`; budget and provider
ride :class:`~pirn_agents.agent.agent_tool_context.AgentToolContext` around
each call.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.agent.agent_tool_context import AgentToolContext
from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.tools.agent_tool import AgentTool
from pirn_agents.tools.tool_status import ToolStatus
from tests.agent_tool_doubles import (
    AGENT_CALLS,
    ROUTE_REGISTRY,
    NestingAgent,
    StubAgent,
    reset_doubles,
)
from tests.conftest import StubLLMProvider


class TestNestingGuard(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_self_referential_graph_terminates_without_recursing_forever(self) -> None:
        # A -> B -> A. The re-entry into A is refused by core's cycle guard
        # (the call is keyed by the agent it wraps), so the graph terminates
        # and the cycle is surfaced rather than hanging.
        with Tapestry():
            a = NestingAgent(_config=KnotConfig(id="A"))
            b = NestingAgent(_config=KnotConfig(id="B"))
        ROUTE_REGISTRY["A"] = b.as_tool()
        ROUTE_REGISTRY["B"] = a.as_tool()

        result = await a.as_tool().run_view({"task": "loop"})

        self.assertIsNotNone(result.result)
        self.assertIn("NestedRunCycleError", result.result.content)
        self.assertEqual(len(AGENT_CALLS["A"]), 1)

    async def test_two_instances_of_one_agent_class_may_nest(self) -> None:
        with Tapestry():
            a = NestingAgent(_config=KnotConfig(id="A"))
            b = NestingAgent(_config=KnotConfig(id="B"))
        ROUTE_REGISTRY["A"] = b.as_tool()  # A -> B (leaf)

        result = await a.as_tool().run_view({"task": "go"})

        self.assertEqual(result.result.content, "A@0->leaf[B]@1")

    async def test_the_depth_cap_is_the_tools_max_depth(self) -> None:
        # A -> B -> C, each a distinct agent, under a cap of one agent-as-tool frame.
        with Tapestry():
            a = NestingAgent(_config=KnotConfig(id="A"))
            b = NestingAgent(_config=KnotConfig(id="B"))
            c = NestingAgent(_config=KnotConfig(id="C"))
        ROUTE_REGISTRY["A"] = b.as_tool()
        ROUTE_REGISTRY["B"] = c.as_tool()

        result = await AgentTool(a, max_depth=1).run_view({"task": "deep"})

        self.assertIsNotNone(result.result)
        self.assertIn("NestingDepthExceededError", result.result.content)

    async def test_context_state_not_leaked_after_a_call(self) -> None:
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"))

        await AgentTool(agent).run_view({"topic": "t"})

        self.assertIsNone(AgentToolContext.bound())


class TestBudgetPropagation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_nested_calls_share_one_meter_two_levels(self) -> None:
        with Tapestry():
            a = NestingAgent(_config=KnotConfig(id="A"))
            b = NestingAgent(_config=KnotConfig(id="B"))
        ROUTE_REGISTRY["A"] = b.as_tool()  # A -> B (leaf)
        meter = RunBudgetMeter(RunBudget(max_iterations=5))

        with AgentToolContext.bind(AgentToolContext(meter=meter)):
            result = await a.as_tool().run_view({"task": "go"})

        # One iteration spent per nested agent entered, across both levels.
        self.assertEqual(meter.iterations, 2)
        self.assertEqual(result.result.content, "A@0->leaf[B]@1")

    async def test_inherited_budget_breach_stops_execution(self) -> None:
        # A shared meter already at its iteration cap: entering the agent
        # breaches the inherited budget before the nested agent runs.
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"))
        meter = RunBudgetMeter(RunBudget(max_iterations=1))
        meter.spend_iteration()  # meter now at the cap

        with AgentToolContext.bind(AgentToolContext(meter=meter)):
            with self.assertRaises(BudgetBreachError):
                await AgentTool(agent).run_view({"topic": "t"})
        # Cancellation token was flipped by the breach.
        self.assertTrue(meter.token.cancelled)
        self.assertNotIn("agent", AGENT_CALLS)

    async def test_tool_level_token_budget_enforced_from_usage(self) -> None:
        # No ambient meter: the tool's own budget builds one, and the nested
        # run's token usage breaches it.
        with Tapestry():
            agent = StubAgent(usage={"total_tokens": 50}, _config=KnotConfig(id="agent"))

        with self.assertRaises(BudgetBreachError):
            await AgentTool(agent, budget=RunBudget(max_tokens=10)).run_view({"topic": "t"})

    async def test_budget_within_limit_succeeds(self) -> None:
        with Tapestry():
            agent = StubAgent(usage={"total_tokens": 5}, _config=KnotConfig(id="agent"))

        result = await AgentTool(
            agent, budget=RunBudget(max_tokens=100, max_iterations=10)
        ).run_view({"topic": "t"})

        self.assertEqual(result.status, ToolStatus.OK)


class TestSharedProviderReuse(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_explicit_provider_injected_into_nested_run(self) -> None:
        pooled = StubLLMProvider(["x"])
        with Tapestry():
            agent = StubAgent(llm=StubLLMProvider(["other"]), _config=KnotConfig(id="agent"))

        await AgentTool(agent, provider=pooled).run_view({"topic": "t"})

        # The nested run reused the pooled provider by identity, not its own.
        self.assertIs(AGENT_CALLS["agent"][0]["llm"], pooled)

    async def test_provider_inherited_across_nesting_by_identity(self) -> None:
        pooled = StubLLMProvider(["x"])
        with Tapestry():
            inner = StubAgent(llm=StubLLMProvider(["ownership"]), _config=KnotConfig(id="inner"))

        # The ambient context's provider propagates into inner even though
        # inner was built with a different provider.
        with AgentToolContext.bind(AgentToolContext(provider=pooled)):
            await AgentTool(inner).run_view({"topic": "deep"})

        self.assertIs(AGENT_CALLS["inner"][0]["llm"], pooled)

    async def test_same_provider_reused_across_repeated_calls(self) -> None:
        pooled = StubLLMProvider(["x"])
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"))
        tool = AgentTool(agent, provider=pooled)

        for _ in range(3):
            await tool.run_view({"topic": "t"})

        used = {id(call["llm"]) for call in AGENT_CALLS["agent"]}
        self.assertEqual(used, {id(pooled)})
