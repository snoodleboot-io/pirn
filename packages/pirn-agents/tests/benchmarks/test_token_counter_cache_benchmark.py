"""Token-counter cache benchmark (PIR-483 / F17-S3-T3).

Validates the caching perf claim: counting the *same* text repeatedly (warm,
cache-hit path) is cheaper than counting equally many *distinct* texts (cold,
estimator-invoked path).
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.context.token_counter import TokenCounter
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.context._stubs import StubWordTokenEstimator


@pytest.mark.benchmark
def test_token_counter_cache_beats_cold_estimation(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    n = 2000
    long_text = " ".join(f"word{i}" for i in range(200))

    # Cold: every call is a distinct string → a cache miss → estimator runs.
    cold_counter = TokenCounter(estimator=StubWordTokenEstimator())
    cold_start = time.perf_counter()
    for i in range(n):
        cold_counter.count(f"{long_text} {i}")
    cold_total = time.perf_counter() - cold_start

    # Warm: one cold miss, then n-1 cache hits (no estimator work).
    warm_counter = TokenCounter(estimator=StubWordTokenEstimator())
    warm_start = time.perf_counter()
    for _ in range(n):
        warm_counter.count(long_text)
    warm_total = time.perf_counter() - warm_start

    assert cold_counter.cache_info()["misses"] == n
    assert warm_counter.cache_info() == {"hits": n - 1, "misses": 1, "size": 1}
    # The cache-hit path must not be slower than cold estimation.
    assert warm_total <= cold_total

    benchmark_recorder.record(
        "TokenCounterCache",
        cold_total=cold_total,
        warm_total=warm_total,
        speedup=cold_total / warm_total if warm_total else 0.0,
    )
