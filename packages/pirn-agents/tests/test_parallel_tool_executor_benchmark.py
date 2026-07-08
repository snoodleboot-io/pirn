"""Throughput micro-benchmark for :class:`ParallelToolExecutor`.

Marked ``@pytest.mark.benchmark`` (marker registered in ``pyproject.toml``).
It deliberately does **not** depend on the pytest-benchmark plugin: wall-clock
is measured directly with :func:`time.perf_counter`. The assertion bound is
loose so the test proves concurrency clearly beats serial execution without
being flaky on a busy CI host. Measured figures are printed so an F10-style
report can harvest them later.
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


class SleepTool(Tool):
    """Fake tool that sleeps a fixed duration then returns a marker."""

    def __init__(self, *, name: str, latency: float) -> None:
        self._name = name
        self._latency = latency

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"sleep {self._latency}s"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        await asyncio.sleep(self._latency)
        return self._name


@pytest.mark.benchmark
async def test_throughput_beats_serial() -> None:
    n = 8
    per_call = 0.05
    tools = [SleepTool(name=f"t{i}", latency=per_call) for i in range(n)]
    toolset = Toolset(tools)
    calls = [ToolCall(tool_name=f"t{i}", arguments={}, call_id=f"c{i}") for i in range(n)]

    with Tapestry():
        executor = ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="pte-bench", validate_io=False),
        )

    start = time.perf_counter()
    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=n, timeout=None, retries=0
    )
    elapsed = time.perf_counter() - start

    assert len(results) == n
    assert all(r.status is ToolStatus.OK for r in results)

    serial = n * per_call
    # Concurrency must clearly beat serial; loose bound keeps it non-flaky.
    assert elapsed < 0.5 * serial

    throughput = n / elapsed
    speedup = serial / elapsed
    print(
        f"[benchmark] ParallelToolExecutor N={n} per_call={per_call}s "
        f"wall={elapsed:.4f}s serial={serial:.4f}s "
        f"throughput={throughput:.1f} calls/s speedup={speedup:.1f}x"
    )
