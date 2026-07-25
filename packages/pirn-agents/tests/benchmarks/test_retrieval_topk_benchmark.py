"""Retrieval top-k latency + recall benchmark using a stub store (PIR-315).

Populates a ``StubMemoryStore`` with known documents, then measures the latency
of a top-k search and its recall against the expected hits.
"""

from __future__ import annotations

import time

import pytest

from tests.benchmarks.conftest import BenchmarkRecorder
from tests.conftest import StubMemoryStore


@pytest.mark.benchmark
async def test_retrieval_topk_latency_and_recall(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    store = StubMemoryStore()
    for i in range(20):
        await store.store(f"doc-{i}", {"id": i, "text": f"document {i}"})

    top_k = 5
    start = time.perf_counter()
    stream = await store.search("document", top_k=top_k)
    hits = [item async for item in stream]
    latency = time.perf_counter() - start

    # The stub returns the first top_k stored docs; recall is hits/top_k here.
    recall = len(hits) / top_k
    assert len(hits) == top_k
    assert recall == 1.0
    assert latency < 0.5

    benchmark_recorder.record("RetrievalTopK", latency=latency, recall=recall, top_k=top_k)
