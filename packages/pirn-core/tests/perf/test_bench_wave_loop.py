"""Benchmark: engine scheduling-loop throughput for chains and wide fan-outs.

Measures total wall-clock time for a single run through a tapestry with many
knots, where each knot does no real work.  The number should be dominated by
Python function-call and asyncio overhead, not pirn framework code.

The file keeps its historical name.  The engine no longer runs in waves: it
schedules each knot as soon as its parents resolve (PIR-841), which removed a
full rescan of the topological order per step and so turned a chain of *n*
knots from O(n^2) into O(n) scheduling work.  The chain cases track that; the
wide case tracks the per-knot cost when everything is ready at once.

Run with:
    pytest tests/perf/bench_wave_loop.py --benchmark-only
"""

from __future__ import annotations

import asyncio

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


@knot
async def _identity(x: int) -> int:
    return x


@knot
async def _add(x: int, y: int) -> int:
    return x + y


def _build_chain_tapestry(n: int):
    """Build a linear chain of n knots: p -> k0 -> k1 -> ... -> k(n-1)."""
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        prev = p
        for i in range(n):
            prev = _identity(x=prev, _config=KnotConfig(id=f"k{i}"))
    return t


def _build_wide_tapestry(n: int):
    """Build a fan-out of n knots that all read one parameter."""
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        for i in range(n):
            _identity(x=p, _config=KnotConfig(id=f"k{i}"))
    return t


def _run_tapestry(t: Tapestry, value: int = 1) -> None:
    asyncio.run(t.run(RunRequest(parameters={"x": value})))


@pytest.mark.benchmark(group="wave-loop")
def test_bench_chain_10(benchmark):
    t = _build_chain_tapestry(10)
    benchmark(_run_tapestry, t)


@pytest.mark.benchmark(group="wave-loop")
def test_bench_chain_100(benchmark):
    t = _build_chain_tapestry(100)
    benchmark(_run_tapestry, t)


@pytest.mark.benchmark(group="wave-loop")
def test_bench_chain_500(benchmark):
    t = _build_chain_tapestry(500)
    benchmark(_run_tapestry, t)


@pytest.mark.benchmark(group="wave-loop")
def test_bench_wide_1000(benchmark):
    t = _build_wide_tapestry(1000)
    benchmark(_run_tapestry, t)
