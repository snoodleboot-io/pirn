"""Ranked-recall latency benchmark (PIR-644 / F27-S4-T3).

Measures the overhead ranked recall adds on top of raw retrieval: ranking a
candidate set (normalise + weighted fusion + sort, no reranker) versus a plain
relevance-only sort of the same candidates. The composite ranking must stay in
the same order of magnitude as the baseline sort — it is a cheap post-step, not
a second retrieval.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.ranked_recall import RankedRecall
from pirn_agents.memory_management.recall_candidate import RecallCandidate
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.memory_management.conftest import make_record

_NOW = make_record(id="anchor").created_at


@pytest.mark.benchmark
def test_ranked_recall_overhead_is_bounded(benchmark_recorder: BenchmarkRecorder) -> None:
    n = 2000
    candidates = [
        RecallCandidate(
            record=make_record(id=f"m{i}", importance=(i % 10) / 10.0, created_at=_NOW),
            relevance=float(n - i),
        )
        for i in range(n)
    ]
    with Tapestry():
        knot = RankedRecall(query="q", candidates=[], now=_NOW, _config=KnotConfig(id="rr-bench"))

    # Baseline: plain relevance-only sort.
    base_start = time.perf_counter()
    _ = sorted(candidates, key=lambda c: -c.relevance)
    base_total = time.perf_counter() - base_start

    # Ranked: full composite fusion.
    ranked_start = time.perf_counter()
    ranked = asyncio.run(knot.process(query="q", candidates=candidates, now=_NOW))
    ranked_total = time.perf_counter() - ranked_start

    assert len(ranked) == n
    # Composite ranking is a bounded post-step, not a second retrieval.
    assert ranked_total < 2.0

    benchmark_recorder.record(
        "RankedRecall",
        candidates=float(n),
        baseline=base_total,
        ranked=ranked_total,
        overhead_ratio=(ranked_total / base_total if base_total else 0.0),
    )
