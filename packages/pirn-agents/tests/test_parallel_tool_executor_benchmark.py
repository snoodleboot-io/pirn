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


class SleepTool(Tool):
    """Fake tool that sleeps a bound duration then returns a bound marker."""

    tool_name: ClassVar[str] = "sleep"

    def __init__(
        self, *, marker: Knot | str, latency: Knot | float, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(marker=marker, latency=latency, _config=_config, **kwargs)

    async def process(self, marker: str, latency: float, **_: Any) -> str:
        await asyncio.sleep(latency)
        return marker


@pytest.mark.benchmark
async def test_throughput_beats_serial() -> None:
    n = 8
    per_call = 0.05
    tools = [
        SleepTool.bind(marker=f"t{i}", latency=per_call).named(
            f"t{i}", description=f"sleep {per_call}s"
        )
        for i in range(n)
    ]
    toolset = Toolset(tools)
    calls = [ToolCall(tool_name=f"t{i}", arguments={}, call_id=f"c{i}") for i in range(n)]

    with Tapestry() as tapestry:
        ParallelToolExecutor(
            tool_calls=calls,
            toolset=toolset,
            max_concurrency=n,
            _config=KnotConfig(id="pte-bench"),
        )

    start = time.perf_counter()
    run = await tapestry.run(RunRequest())
    elapsed = time.perf_counter() - start
    assert run.succeeded, run.exceptions
    results = run.outputs["pte-bench"]

    assert len(results) == n
    assert all(r.status == "ok" for r in results)

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
