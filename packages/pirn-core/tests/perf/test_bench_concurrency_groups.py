"""Benchmark: admission cost against the number of concurrency groups (PIR-841).

A flat fan-out of 10,000 trivial knots is spread over 0, 1,000 and 5,000
groups, unbounded and with every group capped at 1.  Scheduling cost should be
near-flat in the group count: the ready queue keeps a heap of group heads and
parks a saturated group until one of its slots is released, so an admission
touches O(log groups) state rather than every group head.  The deterministic
regression guard is ``TestReadyQueueScaling`` in the unit suite, which counts
offers; this file tracks the wall-clock cost.

Run with:
    pytest tests/perf/test_bench_concurrency_groups.py --benchmark-only -o addopts=""
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


@knot
async def _identity(x: int) -> int:
    return x


def _build_grouped_tapestry(n: int, groups: int) -> Tapestry:
    """Build a fan-out of n knots spread round-robin over *groups* groups."""
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        for i in range(n):
            extra: dict[str, Any] = {}
            if groups:
                extra["concurrency_group"] = f"g{i % groups}"
            _identity(x=p, _config=KnotConfig(id=f"k{i}", **extra))
    return t


def _run_tapestry(t: Tapestry, limits: ConcurrencyLimits | None) -> None:
    asyncio.run(t.run(RunRequest(parameters={"x": 1}, concurrency=limits)))


@pytest.mark.benchmark(group="concurrency-groups")
@pytest.mark.parametrize("groups", [0, 1000, 5000])
def test_bench_unbounded_10k_by_group_count(benchmark: Any, groups: int) -> None:
    t = _build_grouped_tapestry(10_000, groups)
    benchmark.pedantic(_run_tapestry, args=(t, None), rounds=3, iterations=1)


@pytest.mark.benchmark(group="concurrency-groups")
@pytest.mark.parametrize("groups", [1000, 5000])
def test_bench_each_group_capped_at_one_10k(benchmark: Any, groups: int) -> None:
    t = _build_grouped_tapestry(10_000, groups)
    limits = ConcurrencyLimits(groups={f"g{g}": 1 for g in range(groups)})
    benchmark.pedantic(_run_tapestry, args=(t, limits), rounds=3, iterations=1)
