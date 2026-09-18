"""``AgentToolCall`` applies ``max_depth`` and ``budget`` wired from upstream knots.

Both used to be read from the knot's literal config only, so a value produced
by a parent knot was invisible: a wired ``max_depth`` silently became the
default of 8 frames and a wired ``budget`` was never enforced.
"""

from __future__ import annotations

from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.tools.agent_tool_call import AgentToolCall
from tests.agent_tool_doubles import ROUTE_REGISTRY, NestingAgent, StubAgent, reset_doubles


def _messages(run: Any) -> str:
    return " ".join(f"{record.exc_type} {record.message}" for record in run.exceptions)


async def test_wired_max_depth_caps_nesting() -> None:
    reset_doubles()
    with Tapestry():
        a = NestingAgent(_config=KnotConfig(id="A"))
        b = NestingAgent(_config=KnotConfig(id="B"))
        c = NestingAgent(_config=KnotConfig(id="C"))
    ROUTE_REGISTRY["A"] = b.as_tool()
    ROUTE_REGISTRY["B"] = c.as_tool()

    with Tapestry() as t:
        depth = Parameter("depth", int, default=1, _config=KnotConfig(id="depth"))
        AgentToolCall(
            arguments={"task": "deep"},
            agent_class=NestingAgent,
            tool_name="A",
            agent_id="A",
            max_depth=depth,
            _config=KnotConfig(id="call"),
        )
    run = await t.run(RunRequest())

    output = run.outputs.get("call")
    rendered = f"{output.data if output is not None else ''} {_messages(run)}"
    assert "NestingDepthExceededError" in rendered


async def test_wired_budget_is_enforced() -> None:
    reset_doubles()
    with Tapestry() as t:
        budget = Parameter(
            "budget", RunBudget, default=RunBudget(max_tokens=10), _config=KnotConfig(id="budget")
        )
        AgentToolCall(
            arguments={"topic": "t"},
            agent_class=StubAgent,
            tool_name="agent",
            bound={"usage": {"total_tokens": 50}},
            budget=budget,
            _config=KnotConfig(id="call"),
        )
    with pytest.raises(BudgetBreachError):
        await t.run(RunRequest())
