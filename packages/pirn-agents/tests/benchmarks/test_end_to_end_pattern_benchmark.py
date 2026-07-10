"""End-to-end pattern latency + token-count benchmark (PIR-321).

Drives a small representative agentic loop — an LLM decision per turn plus a
tool call — entirely on stub doubles for determinism, measuring wall-clock
latency and a summed token count across the run. Token usage is enforced through
a shared :class:`RunBudgetMeter`, exercising the budget primitive on the hot
path without breaching.
"""

from __future__ import annotations

import time

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.conftest import StubLLMProvider, StubTool


@pytest.mark.benchmark
async def test_end_to_end_pattern_latency_and_tokens(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    turns = 4
    tokens_per_turn = 10
    provider = StubLLMProvider(["use tool"] * turns + ["done"])
    toolset = Toolset([StubTool(name="search", handler="hit")])
    meter = RunBudgetMeter(RunBudget(max_iterations=turns + 1, max_tokens=1000))

    with Tapestry():
        executor = ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="pte-e2e", validate_io=False),
        )

    start = time.perf_counter()
    total_tokens = 0
    for turn in range(turns):
        meter.spend_iteration()
        await provider.chat([{"role": "user", "content": f"turn {turn}"}])
        meter.spend_tokens(tokens_per_turn)
        total_tokens += tokens_per_turn
        results = await executor.process(
            tool_calls=[ToolCall(tool_name="search", arguments={"q": "x"}, call_id=f"c{turn}")],
            toolset=toolset,
            max_concurrency=1,
            timeout=None,
            retries=0,
        )
        assert results[0].status is ToolStatus.OK
    latency = time.perf_counter() - start

    assert total_tokens == turns * tokens_per_turn
    assert meter.iterations == turns  # budget never breached
    assert latency < 1.0

    benchmark_recorder.record(
        "EndToEndPattern",
        wall=latency,
        turns=turns,
        tokens=total_tokens,
    )
