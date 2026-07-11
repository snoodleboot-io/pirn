"""Tests for :func:`pirn_agents.agent_invocation.invoke_agent`.

Covers the recursion/cycle guard (F7-S3), budget propagation (F7-S4), and
shared provider reuse (F7-S5) that the shared machinery enforces.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.agent_invocation import invoke_agent
from pirn_agents.agent_schema import default_agent_schema
from pirn_agents.agent_tool_context import (
    AgentToolContext,
    bind_agent_tool_context,
    current_agent_tool_context,
)
from pirn_agents.exceptions.agent_cycle_error import AgentCycleError
from pirn_agents.exceptions.agent_depth_exceeded_error import (
    AgentDepthExceededError,
)
from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.types.tool_status import ToolStatus
from tests.agent_tool_doubles import (
    AGENT_CALLS,
    ROUTE_REGISTRY,
    NestingAgent,
    StubAgent,
    reset_doubles,
)
from tests.conftest import StubLLMProvider


def _schema() -> dict[str, object]:
    return {"type": "object", "properties": {"topic": {"type": "string"}}}


class TestRecursionGuard(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    def _agent(self, id_: str = "agent") -> StubAgent:
        with Tapestry():
            return StubAgent(_config=KnotConfig(id=id_))

    async def test_raises_depth_error_at_cap(self) -> None:
        agent = self._agent()
        at_cap = AgentToolContext(depth=2, stack=("x", "y"), max_depth=2)

        with bind_agent_tool_context(at_cap):
            with self.assertRaises(AgentDepthExceededError):
                await invoke_agent(agent, {"topic": "t"}, name="a", schema=_schema())

    async def test_raises_cycle_error_when_agent_already_active(self) -> None:
        agent = self._agent()
        active = AgentToolContext(depth=1, stack=(agent.knot_id,), max_depth=8)

        with bind_agent_tool_context(active):
            with self.assertRaises(AgentCycleError):
                await invoke_agent(agent, {"topic": "t"}, name="a", schema=_schema())

    async def test_depth_state_not_leaked_after_invocation(self) -> None:
        agent = self._agent()

        await invoke_agent(agent, {"topic": "t"}, name="a", schema=_schema())

        self.assertIsNone(current_agent_tool_context())

    async def test_self_referential_graph_terminates_without_recursing_forever(self) -> None:
        # A -> B -> A. The re-entry into A is rejected by the cycle guard, so the
        # graph terminates and the cycle is surfaced rather than hanging.
        with Tapestry():
            a = NestingAgent(_config=KnotConfig(id="A"))
            b = NestingAgent(_config=KnotConfig(id="B"))
        ROUTE_REGISTRY["A"] = b.as_tool()
        ROUTE_REGISTRY["B"] = a.as_tool()

        result = await a.as_tool().invoke({"task": "loop"})

        self.assertIsNotNone(result.result)
        self.assertIn("AgentCycleError", result.result.content)


class TestBudgetPropagation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_nested_calls_share_one_meter_two_levels(self) -> None:
        with Tapestry():
            a = NestingAgent(_config=KnotConfig(id="A"))
            b = NestingAgent(_config=KnotConfig(id="B"))
        ROUTE_REGISTRY["A"] = b.as_tool()  # A -> B (leaf)
        meter = RunBudgetMeter(RunBudget(max_iterations=5))

        with bind_agent_tool_context(AgentToolContext(max_depth=8, meter=meter)):
            result = await a.as_tool().invoke({"task": "go"})

        # One iteration spent per nested agent entered, across both levels.
        self.assertEqual(meter.iterations, 2)
        self.assertEqual(result.result.content, "A@1->leaf[B]@2")

    async def test_inherited_budget_breach_stops_execution(self) -> None:
        # A shared meter already at its iteration cap: entering the agent
        # breaches the inherited budget before the nested agent runs.
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"))
        meter = RunBudgetMeter(RunBudget(max_iterations=1))
        meter.spend_iteration()  # meter now at the cap

        with bind_agent_tool_context(AgentToolContext(max_depth=8, meter=meter)):
            with self.assertRaises(BudgetBreachError):
                await invoke_agent(agent, {"topic": "t"}, name="a", schema=_schema())
        # Cancellation token was flipped by the breach.
        self.assertTrue(meter.token.cancelled)

    async def test_tool_level_token_budget_enforced_from_usage(self) -> None:
        # No ambient meter: the tool's own budget builds one, and the nested
        # run's token usage breaches it.
        with Tapestry():
            agent = StubAgent(usage={"total_tokens": 50}, _config=KnotConfig(id="agent"))

        with self.assertRaises(BudgetBreachError):
            await invoke_agent(
                agent,
                {"topic": "t"},
                name="a",
                schema=_schema(),
                budget=RunBudget(max_tokens=10),
            )

    async def test_budget_within_limit_succeeds(self) -> None:
        with Tapestry():
            agent = StubAgent(usage={"total_tokens": 5}, _config=KnotConfig(id="agent"))

        result = await invoke_agent(
            agent,
            {"topic": "t"},
            name="a",
            schema=_schema(),
            budget=RunBudget(max_tokens=100, max_iterations=10),
        )

        self.assertEqual(result.status, ToolStatus.OK)


class TestSharedProviderReuse(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_doubles()

    async def test_explicit_provider_injected_into_nested_run(self) -> None:
        pooled = StubLLMProvider(["x"])
        with Tapestry():
            agent = StubAgent(llm=StubLLMProvider(["other"]), _config=KnotConfig(id="agent"))

        await invoke_agent(agent, {"topic": "t"}, name="a", schema=_schema(), provider=pooled)

        # The nested run reused the pooled provider by identity, not its own.
        self.assertIs(AGENT_CALLS["agent"][0]["llm"], pooled)

    async def test_provider_inherited_across_nesting_by_identity(self) -> None:
        pooled = StubLLMProvider(["x"])
        with Tapestry():
            outer = StubAgent(reply="outer", _config=KnotConfig(id="outer"))
            inner = StubAgent(llm=StubLLMProvider(["ownership"]), _config=KnotConfig(id="inner"))

        # outer's provider propagates into inner even though inner was built
        # with a different provider.
        context = AgentToolContext(max_depth=8, provider=pooled)
        with bind_agent_tool_context(context):
            await invoke_agent(inner, {"topic": "deep"}, name="inner", schema=_schema())

        self.assertIs(AGENT_CALLS["inner"][0]["llm"], pooled)

    async def test_same_provider_reused_across_repeated_invocations(self) -> None:
        pooled = StubLLMProvider(["x"])
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"))

        for _ in range(3):
            await invoke_agent(agent, {"topic": "t"}, name="a", schema=_schema(), provider=pooled)

        used = {id(call["llm"]) for call in AGENT_CALLS["agent"]}
        self.assertEqual(used, {id(pooled)})
