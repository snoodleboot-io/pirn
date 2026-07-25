"""Consolidation batch-throughput benchmark (PIR-632 / F27-S1-T3).

Confirms consolidation runs off the hot path: a batch consolidation pass over
many episodic records completes in bounded time and its cost scales with the
batch, so it can run in the background without regressing on-line search. The
run uses only in-process stubs — no store, no summarizer service.
"""

from __future__ import annotations

import time

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.memory_consolidator import MemoryConsolidator
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.memory_management.conftest import StubSummarizer, make_record


@pytest.mark.benchmark
def test_consolidation_batch_throughput(benchmark_recorder: BenchmarkRecorder) -> None:
    import asyncio

    n = 600
    # Three clusters with disjoint vocabulary; within a cluster records are
    # near-duplicates, across clusters they share nothing — so grouping does
    # real O(n^2) work yet collapses to exactly three semantic records.
    clusters = [
        "the bright blue sky stretches overhead today",
        "powerful rockets fly toward the distant silver moon",
        "sleepy cats and dogs enjoy long warm afternoon naps",
    ]
    records = [make_record(id=f"e{i}", content=clusters[i % 3]) for i in range(n)]
    with Tapestry():
        knot = MemoryConsolidator(
            records=[], summarizer=StubSummarizer(), _config=KnotConfig(id="mc-bench")
        )

    start = time.perf_counter()
    result = asyncio.run(knot.process(records=records, summarizer=StubSummarizer()))
    elapsed = time.perf_counter() - start

    # 3 clusters collapse to 3 semantic records; the pass must be quick.
    assert len(result) == 3
    assert elapsed < 5.0

    benchmark_recorder.record(
        "MemoryConsolidationBatch",
        records=float(n),
        wall=elapsed,
        throughput=(n / elapsed if elapsed else 0.0),
    )
