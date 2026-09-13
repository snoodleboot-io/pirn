"""Orchestrator-workers scaling micro-benchmark (PIR-235).

``@pytest.mark.benchmark``; bounded-concurrency fan-out finishes a batch of
sleeping workers far faster than serial, proving worker throughput scales with
the concurrency cap.
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

from pirn_agents.specializations.multi_agent.orchestrator_workers import OrchestratorWorkers
from pirn_agents.tools.tool import Tool
from tests.benchmarks.conftest import BenchmarkRecorder


class _SleepWorker(Tool):
    """Sleep a bound latency, then echo the task."""

    tool_name: ClassVar[str] = "sleep_worker"

    def __init__(
        self, *, task: Knot | str, latency: Knot | float, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(task=task, latency=latency, _config=_config, **kwargs)

    async def process(self, task: str, latency: float, **_: Any) -> str:
        await asyncio.sleep(latency)
        return task


@pytest.mark.benchmark
async def test_orchestrator_workers_scaling(benchmark_recorder: BenchmarkRecorder) -> None:
    n = 8
    per_task = 0.02
    worker = _SleepWorker.bind(latency=per_task)
    tasks = tuple(f"t{i}" for i in range(n))

    start = time.perf_counter()
    with Tapestry() as t:
        OrchestratorWorkers(
            tasks=tasks, worker=worker, max_concurrency=n, _config=KnotConfig(id="ow")
        )
    run = await t.run(RunRequest())
    elapsed = time.perf_counter() - start

    assert run.succeeded
    result = run.outputs["ow"]
    assert result.total == n
    serial = n * per_task
    assert elapsed < 0.5 * serial  # loose, non-flaky

    benchmark_recorder.record(
        "OrchestratorWorkersScaling",
        wall=elapsed,
        serial=serial,
        workers=float(n),
        speedup=serial / elapsed,
    )
    report = benchmark_recorder.report()
    assert report.metric("OrchestratorWorkersScaling", "speedup") is not None
