"""Tool-executor throughput benchmark using the shared harness (PIR-315).

``@pytest.mark.benchmark``; wall-clock is measured with
:func:`time.perf_counter` (no pytest-benchmark plugin). The bound is loose so it
proves concurrency beats serial without being flaky on a busy CI host.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, ClassVar

import pytest
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.toolset import Toolset
from tests.benchmarks.conftest import BenchmarkRecorder


class _SleepTool(Tool):
    """Sleep a bound duration, then return the bound marker."""

    tool_name: ClassVar[str] = "sleep"

    def __init__(
        self, *, marker: Knot | str, latency: Knot | float, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(marker=marker, latency=latency, _config=_config, **kwargs)

    async def process(self, marker: str, latency: float, **_: Any) -> str:
        await asyncio.sleep(latency)
        return marker


@pytest.mark.benchmark
async def test_tool_executor_throughput(benchmark_recorder: BenchmarkRecorder) -> None:
    n = 8
    per_call = 0.02
    toolset = Toolset(
        [
            _SleepTool.bind(marker=f"t{i}", latency=per_call).named(f"t{i}", description="sleep")
            for i in range(n)
        ]
    )
    calls = [ToolCall(tool_name=f"t{i}", arguments={}, call_id=f"c{i}") for i in range(n)]

    with Tapestry() as tapestry:
        ParallelToolExecutor(
            tool_calls=calls,
            toolset=toolset,
            max_concurrency=n,
            _config=KnotConfig(id="pte-bench-harness"),
        )
    start = time.perf_counter()
    run = await tapestry.run(RunRequest())
    elapsed = time.perf_counter() - start
    assert run.succeeded, run.exceptions
    results = run.outputs["pte-bench-harness"]

    assert all(r.status == "ok" for r in results)
    serial = n * per_call
    assert elapsed < 0.5 * serial  # loose, non-flaky

    benchmark_recorder.record(
        "ToolExecutorThroughput",
        wall=elapsed,
        serial=serial,
        throughput=n / elapsed,
        speedup=serial / elapsed,
    )
    report = benchmark_recorder.report()
    assert report.metric("ToolExecutorThroughput", "speedup") is not None
