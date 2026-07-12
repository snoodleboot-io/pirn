"""ContextAssembler scaling benchmark (PIR-486 / F17-S4-T3).

Measures assembly time across growing item counts under both the fits-the-budget
(no-eviction, O(n)) path and the eviction path to validate near-linear scaling.
"""

from __future__ import annotations

import time

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.context.context_assembler import ContextAssembler
from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.token_counter import TokenCounter
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.context._stubs import StubWordTokenEstimator


def _assembler() -> ContextAssembler:
    @knot
    async def _items() -> tuple:
        return ()

    @knot
    async def _counter() -> TokenCounter:
        return TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=0)

    with Tapestry():
        return ContextAssembler(
            items=_items(_config=KnotConfig(id="items")),
            budget=10,
            counter=_counter(_config=KnotConfig(id="counter")),
            _config=KnotConfig(id="assemble"),
        )


def _items(n: int) -> tuple[ContextItem, ...]:
    return tuple(ContextItem(content=f"tok tok {i}", position=i) for i in range(n))


async def _time_assembly(n: int, budget: int) -> float:
    assembler = _assembler()
    counter = TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=0)
    items = _items(n)
    start = time.perf_counter()
    await assembler.process(items=items, budget=budget, counter=counter)
    return time.perf_counter() - start


@pytest.mark.benchmark
async def test_assembler_scales_near_linearly(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    # Large budget → no eviction → pure O(n) sizing pass.
    small = await _time_assembly(500, budget=10_000_000)
    large = await _time_assembly(5000, budget=10_000_000)

    # 10x the items should be well under 30x the time (allows constant overhead).
    ratio = large / small if small else 0.0
    assert ratio < 30

    # Eviction path (tight budget) still completes for a large input.
    evict = await _time_assembly(5000, budget=10)
    assert evict < 1.0

    benchmark_recorder.record(
        "ContextAssemblerScaling",
        n500=small,
        n5000=large,
        ratio=ratio,
        evict5000=evict,
    )
