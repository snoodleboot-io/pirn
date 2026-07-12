"""Reflexion iterations-to-success micro-benchmark (PIR-211).

``@pytest.mark.benchmark``; measures how many actor attempts the memory-backed
Reflexion loop needs before the evaluator accepts, under the stub provider.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.reflexion.reflexion_pipeline import ReflexionPipeline
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.specializations.conftest import StubLLMProvider


class _DictMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._data: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self._data[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self._data.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            return
            yield {}

        return _aiter()

    async def forget(self, key: str) -> None:
        self._data.pop(key, None)

    async def close(self) -> None:
        return None


@pytest.mark.benchmark
async def test_reflexion_iterations_to_success(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    # Two failed attempts then success on the third.
    llm = StubLLMProvider(["a1", "FAIL: x", "r1", "a2", "FAIL: y", "r2", "a3", "PASS"])
    with Tapestry() as t:
        ReflexionPipeline(
            task="fixture task",
            llm=llm,
            memory=_DictMemoryStore(),
            max_iterations=5,
            _config=KnotConfig(id="rx"),
        )
    run = await t.run(RunRequest())
    assert run.succeeded
    result = run.outputs["rx"]
    assert result.succeeded is True

    benchmark_recorder.record(
        "ReflexionIterationsToSuccess",
        iterations=result.iterations,
        succeeded=1.0 if result.succeeded else 0.0,
    )
    report = benchmark_recorder.report()
    assert report.metric("ReflexionIterationsToSuccess", "iterations") == 3
