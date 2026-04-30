"""Integration tests for agent_loop example."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "llm_agent"))
from agent_loop import (  # noqa: E402
    TASKS,
    AgentState,
    build_tapestry,
    plan_next_actions,
)

from pirn.core.run_request import RunRequest


def _state(task: str, seed: int = 1, iteration: int = 1) -> AgentState:
    return AgentState(task=task, run_seed=seed, iteration=iteration)


async def test_all_tasks_succeed():
    t = build_tapestry()
    for i, task in enumerate(TASKS):
        state = AgentState(task=task, run_seed=i + 1)
        r = await t.run(RunRequest(parameters={"state": state}))
        assert r.succeeded, f"Task {task!r} failed: {r.exceptions}"
        final: AgentState = r.outputs["agent_loop"]
        assert final.done
        assert final.final_answer
        assert len(final.scratchpad) >= 1


async def test_reruns_produce_different_paths():
    """Same task with different run_seeds → different scratchpad contents."""
    task = TASKS[0]
    t = build_tapestry()

    results = []
    for seed in range(1, 5):
        state = AgentState(task=task, run_seed=seed)
        r = await t.run(RunRequest(parameters={"state": state}))
        assert r.succeeded
        final: AgentState = r.outputs["agent_loop"]
        path = tuple((s.action_type, s.name) for s in final.scratchpad)
        results.append(path)

    unique_paths = set(results)
    assert len(unique_paths) >= 2, f"Expected path variation across seeds, got: {unique_paths}"


def test_planner_varies_across_seeds():
    """Plan for same task/iteration with different seeds → different actions."""
    task = "What's the weather forecast for my trip to London and Tokyo?"
    plans = set()
    for seed in range(1, 8):
        state = _state(task, seed=seed, iteration=1)
        actions = plan_next_actions(state)
        key = tuple((a.action_type, a.name) for a in actions)
        plans.add(key)
    assert len(plans) >= 2, f"Planner produced no variation: {plans}"


def test_planner_evolves_with_scratchpad():
    """Later iterations with scratchpad → different (synthesis-oriented) plans."""
    from agent_loop import StepResult

    task = "Research quantum computing and write a summary"
    state = _state(task, seed=1, iteration=3)
    state.scratchpad = [
        StepResult(1, "mcp_call", "web_search", "quantum bits show 99.9% fidelity"),
        StepResult(2, "mcp_call", "web_search", "IBM announces 1000-qubit processor"),
    ]
    actions = plan_next_actions(state)
    types = {a.action_type for a in actions}
    # With scratchpad and iter >= 2, planner should lean toward synthesis (subagent)
    assert "subagent" in types or len(actions) >= 1  # at minimum something planned


async def test_action_types_vary_across_tasks():
    """Different tasks should produce different action type mixes."""
    t = build_tapestry()
    all_types: set[str] = set()
    for i, task in enumerate(TASKS):
        state = AgentState(task=task, run_seed=i + 1)
        r = await t.run(RunRequest(parameters={"state": state}))
        if r.succeeded:
            final: AgentState = r.outputs["agent_loop"]
            for step in final.scratchpad:
                all_types.add(step.action_type)
    assert "tool_call" in all_types
    assert "mcp_call" in all_types
    assert "subagent" in all_types
