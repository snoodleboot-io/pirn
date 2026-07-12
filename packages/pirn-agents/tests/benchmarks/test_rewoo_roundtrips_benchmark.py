"""ReWOO vs. ReAct LLM round-trip micro-benchmark (PIR-202).

``@pytest.mark.benchmark``; asserts the ReWOO pattern issues strictly fewer LLM
round-trips than a ReAct loop on the same fixture multi-tool task. ReWOO pays a
fixed two round-trips (plan + synthesise) while ReAct pays one per step.
"""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.specializations.rewoo.rewoo_pipeline import ReWooPipeline
from pirn_agents.types.agent_message import AgentMessage
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.specializations.conftest import StubLLMProvider, StubTool


@pytest.mark.benchmark
async def test_rewoo_fewer_round_trips_than_react(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    n_tools = 4

    # ReWOO: plan lists all tools, then one synthesis. Two round-trips total.
    rewoo_llm = StubLLMProvider(
        ["\n".join(f"{i + 1}. search: q{i}" for i in range(n_tools)), "final answer"]
    )
    with Tapestry() as rewoo_t:
        ReWooPipeline(
            goal="multi-tool task",
            llm=rewoo_llm,
            tools=(StubTool(name="search", handler="hit"),),
            _config=KnotConfig(id="rewoo"),
        )
    rewoo_run = await rewoo_t.run(RunRequest())
    assert rewoo_run.succeeded
    rewoo_round_trips = len(rewoo_llm.calls)

    # ReAct: one LLM round-trip per unrolled step on the same task.
    react_llm = StubLLMProvider([f"Action: search\nAction Input: q{i}" for i in range(n_tools)])
    with Tapestry() as react_t:
        ReActLoop(
            messages=(AgentMessage(role="user", content="multi-tool task"),),
            llm=react_llm,
            tools=(StubTool(name="search", handler="hit"),),
            max_iterations=n_tools,
            _config=KnotConfig(id="react"),
        )
    await react_t.run(RunRequest())
    react_round_trips = len(react_llm.calls)

    assert rewoo_round_trips == 2
    assert rewoo_round_trips < react_round_trips

    benchmark_recorder.record(
        "ReWooVsReActRoundTrips",
        rewoo_round_trips=rewoo_round_trips,
        react_round_trips=react_round_trips,
        savings=react_round_trips - rewoo_round_trips,
    )
    report = benchmark_recorder.report()
    assert report.metric("ReWooVsReActRoundTrips", "savings") is not None
