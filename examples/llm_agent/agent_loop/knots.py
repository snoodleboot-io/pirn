"""Knot factories for the ``examples.llm_agent.agent_loop`` example.

``run_tool_call`` and ``run_mcp_call`` are the two leaf action knots the planner
registers directly into the running tapestry.  ``prepare_context`` and
``execute_subagent`` are the two steps of the inner tapestry
``SubAgentRunner`` builds; they take the action and the session context as
literal inputs rather than closing over them, so the sub-agent pipeline is
written once here instead of being redefined on every ``process()`` call.
"""

from __future__ import annotations

import asyncio

from pirn.core.knot_factory import KnotFactory

from examples.llm_agent.agent_loop.fake_backends import FakeBackends
from examples.llm_agent.agent_loop.planned_action import PlannedAction
from examples.llm_agent.agent_loop.session_context import SessionContext
from examples.llm_agent.agent_loop.step_result import StepResult


@KnotFactory.knot
async def run_tool_call(action: PlannedAction, ctx: SessionContext, **_) -> StepResult:
    """Execute a local tool function."""
    output = FakeBackends.tool(action.name, action.args, ctx.rng(extra=action.name))
    return StepResult(
        iteration=ctx.iteration,
        msg_idx=ctx.msg_idx,
        action_type="tool_call",
        name=action.name,
        output=output,
    )


@KnotFactory.knot
async def run_mcp_call(action: PlannedAction, ctx: SessionContext, **_) -> StepResult:
    """Execute a remote MCP service call (simulated)."""
    await asyncio.sleep(0)
    output = FakeBackends.mcp(action.name, action.args, ctx.rng(extra=action.name))
    return StepResult(
        iteration=ctx.iteration,
        msg_idx=ctx.msg_idx,
        action_type="mcp_call",
        name=action.name,
        output=output,
    )


@KnotFactory.knot
async def prepare_context(raw: str, **_) -> str:
    """First step of the sub-agent inner tapestry: trim the inherited context."""
    return raw[:300].strip()


@KnotFactory.knot
async def execute_subagent(
    prepared: str, action: PlannedAction, ctx: SessionContext, **_
) -> StepResult:
    """Second step of the sub-agent inner tapestry: run the sub-agent itself."""
    rng = ctx.rng(extra=action.name)
    raw_output = FakeBackends.subagent(action.name, action.args, prepared, rng)
    return StepResult(
        iteration=ctx.iteration,
        msg_idx=ctx.msg_idx,
        action_type="subagent",
        name=action.name,
        output=raw_output,
    )
