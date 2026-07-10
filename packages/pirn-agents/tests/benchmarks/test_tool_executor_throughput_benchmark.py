"""Tool-executor throughput benchmark using the shared harness (PIR-315).

``@pytest.mark.benchmark``; wall-clock is measured with
:func:`time.perf_counter` (no pytest-benchmark plugin). The bound is loose so it
proves concurrency beats serial without being flaky on a busy CI host.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus
from tests.benchmarks.conftest import BenchmarkRecorder


class _SleepTool(Tool):
    def __init__(self, *, name: str, latency: float) -> None:
        self._name = name
        self._latency = latency

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "sleep"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        await asyncio.sleep(self._latency)
        return self._name


@pytest.mark.benchmark
async def test_tool_executor_throughput(benchmark_recorder: BenchmarkRecorder) -> None:
    n = 8
    per_call = 0.02
    toolset = Toolset([_SleepTool(name=f"t{i}", latency=per_call) for i in range(n)])
    calls = [ToolCall(tool_name=f"t{i}", arguments={}, call_id=f"c{i}") for i in range(n)]

    with Tapestry():
        executor = ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="pte-bench-harness", validate_io=False),
        )

    start = time.perf_counter()
    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=n, timeout=None, retries=0
    )
    elapsed = time.perf_counter() - start

    assert all(r.status is ToolStatus.OK for r in results)
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
