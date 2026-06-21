"""Benchmark: wave-loop throughput for a wide tapestry.

Measures total wall-clock time for a single run through a tapestry with many
knots, where each knot does no real work.  The number should be dominated by
Python function-call and asyncio overhead, not pirn framework code.

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
