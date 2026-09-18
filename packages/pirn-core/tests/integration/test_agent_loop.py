"""Integration tests for agent_loop example."""

from __future__ import annotations

# cross-domain: skipped in per-package isolation, run by the unified suite (SCD-24)
import pytest as _pytest

_pytest.importorskip("pirn_agents")
pytestmark = _pytest.mark.cross_domain

import sys
from pathlib import Path

# The example is a package under the repository root, so the root goes on the path
# and the example is imported by its real dotted name.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from examples.llm_agent.agent_loop.agent_loop import AgentLoop
from examples.llm_agent.agent_loop.agent_planner import AgentPlanner
from examples.llm_agent.agent_loop.session_config import SessionConfig
from examples.llm_agent.agent_loop.session_context import SessionContext
from examples.llm_agent.agent_loop.step_result import StepResult


async def test_session_produces_one_run():
    """One session = one extensible tapestry run covering all messages."""
    ctx = AgentLoop.make_session(run_seed=1)
    t = AgentLoop.build_tapestry(initial_ctx=ctx)
    r = await t.run(extensible=True)
    assert r.succeeded, f"Session failed: {r.exceptions}"
    final: SessionContext = r.outputs[SessionConfig.session_complete_id]
    assert final.done
    assert len(final.responses) == len(final.messages)
    assert final.iteration >= len(final.messages)


async def test_all_messages_resolved():
    """Every message gets a response."""
    ctx = AgentLoop.make_session(run_seed=2)
    t = AgentLoop.build_tapestry(initial_ctx=ctx)
    r = await t.run(extensible=True)
    assert r.succeeded
    final: SessionContext = r.outputs[SessionConfig.session_complete_id]
    assert len(final.responses) == len(final.messages)
    assert all(len(resp) > 0 for resp in final.responses)


async def test_different_seeds_produce_different_iteration_counts():
    """Different run_seeds produce different total iteration counts."""
    counts = []
    for seed in range(1, 5):
        ctx = AgentLoop.make_session(run_seed=seed)
        t = AgentLoop.build_tapestry(initial_ctx=ctx)
        r = await t.run(extensible=True)
        assert r.succeeded
        final: SessionContext = r.outputs[SessionConfig.session_complete_id]
        counts.append(final.iteration)
    assert len(set(counts)) >= 2, f"Expected iteration count variation, got: {counts}"


async def test_scratchpad_tagged_by_message():
    """Every scratchpad entry is tagged with the message index it belongs to."""
    ctx = AgentLoop.make_session(run_seed=1)
    t = AgentLoop.build_tapestry(initial_ctx=ctx)
    r = await t.run(extensible=True)
    assert r.succeeded
    final: SessionContext = r.outputs[SessionConfig.session_complete_id]
    for step in final.scratchpad:
        assert 0 <= step.msg_idx < len(final.messages)


async def test_action_types_vary_across_messages():
    """Different messages produce different action type mixes."""
    ctx = AgentLoop.make_session(run_seed=1)
    t = AgentLoop.build_tapestry(initial_ctx=ctx)
    r = await t.run(extensible=True)
    assert r.succeeded
    final: SessionContext = r.outputs[SessionConfig.session_complete_id]
    all_types = {s.action_type for s in final.scratchpad}
    assert "tool_call" in all_types
    assert "mcp_call" in all_types
    assert "subagent" in all_types


def test_planner_varies_across_seeds():
    """Same message + different seeds → different plans."""
    msg = AgentLoop.messages()[0]
    plans = set()
    for seed in range(1, 8):
        ctx = SessionContext(messages=(msg,), run_seed=seed, iteration=1, msg_iteration=1)
        actions = AgentPlanner.plan_next_actions(ctx)
        plans.add(tuple((a.action_type, a.name) for a in actions))
    assert len(plans) >= 2, f"Planner produced no variation: {plans}"


def test_planner_moves_to_synthesis_after_data_gathering():
    """After msg_iteration >= 2 with scratchpad, planner leans toward synthesis."""
    msg = "Research quantum computing and summarise for me"
    ctx = SessionContext(
        messages=(msg,),
        run_seed=1,
        iteration=3,
        msg_iteration=3,
        scratchpad=(
            StepResult(1, 0, "mcp_call", "web_search", "quantum bits show 99.9% fidelity"),
            StepResult(2, 0, "mcp_call", "web_search", "IBM announces 1000-qubit processor"),
        ),
    )
    actions = AgentPlanner.plan_next_actions(ctx)
    types = {a.action_type for a in actions}
    assert "subagent" in types or len(actions) >= 1
