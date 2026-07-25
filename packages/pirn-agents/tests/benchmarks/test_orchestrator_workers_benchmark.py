"""Orchestrator-workers scaling micro-benchmark (PIR-235).

``@pytest.mark.benchmark``; bounded-concurrency fan-out finishes a batch of
sleeping workers far faster than serial, proving worker throughput scales with
the concurrency cap.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.orchestrator_workers import OrchestratorWorkers
from pirn_agents.tool import Tool
from tests.benchmarks.conftest import BenchmarkRecorder


class _SleepWorker(Tool):
    def __init__(self, latency: float) -> None:
        self._latency = latency

    @property
    def name(self) -> str:
        return "sleep_worker"

    @property
    def description(self) -> str:
        return "sleep"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {"task": {"type": "string"}}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        await asyncio.sleep(self._latency)
        return arguments["task"]


@pytest.mark.benchmark
async def test_orchestrator_workers_scaling(benchmark_recorder: BenchmarkRecorder) -> None:
    n = 8
    per_task = 0.02
    worker = _SleepWorker(per_task)
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
