"""Benchmark: status-event fanout with many emitters.

Measures the overhead of dispatching a single StatusEvent to N emitters.
Identifies whether the per-emitter dispatch (currently synchronous iteration)
is a bottleneck at scale.

Run with:
    pytest tests/perf/bench_status_fanout.py --benchmark-only
"""

from __future__ import annotations

import asyncio

import pytest

from pirn import KnotConfig, Parameter, RunRequest, Tapestry, knot
from pirn.managers.status import KnotState, StatusEvent


def _noop_emitter(event: StatusEvent) -> None:
    pass


async def _async_noop_emitter(event: StatusEvent) -> None:
    pass


def _build_tapestry_with_emitters(n: int, async_emitters: bool = False):
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _identity(x=p, _config=KnotConfig(id="k"))
    for _ in range(n):
        emitter = _async_noop_emitter if async_emitters else _noop_emitter
        t.add_emitter(emitter)
    return t


@knot
async def _identity(x: int) -> int:
    return x


@pytest.mark.benchmark(group="fanout-sync")
def test_bench_fanout_10_sync(benchmark):
    t = _build_tapestry_with_emitters(10)
    benchmark(lambda: asyncio.run(t.run(RunRequest(parameters={"x": 1}))))


@pytest.mark.benchmark(group="fanout-sync")
def test_bench_fanout_100_sync(benchmark):
    t = _build_tapestry_with_emitters(100)
    benchmark(lambda: asyncio.run(t.run(RunRequest(parameters={"x": 1}))))


@pytest.mark.benchmark(group="fanout-async")
def test_bench_fanout_10_async(benchmark):
    t = _build_tapestry_with_emitters(10, async_emitters=True)
    benchmark(lambda: asyncio.run(t.run(RunRequest(parameters={"x": 1}))))


@pytest.mark.benchmark(group="fanout-async")
def test_bench_fanout_100_async(benchmark):
    t = _build_tapestry_with_emitters(100, async_emitters=True)
    benchmark(lambda: asyncio.run(t.run(RunRequest(parameters={"x": 1}))))
