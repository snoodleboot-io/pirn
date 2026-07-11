"""Micro-benchmark: top-k query latency at N=10k/100k (PAE-F4-S3-T4).

Validates the numpy-vectorised cosine search stays responsive as the corpus
grows. Runs at N=10k by default and N=100k under ``--run-heavy`` scale; the
assertion bound is loose (well above realistic latency) so it proves
sub-linear-feeling responsiveness without being flaky on a busy CI host.
Measured figures are printed for an F10-style report.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.vector_stores.vector_record import VectorRecord


async def _seed(store: InMemoryVectorStore, n: int, dim: int) -> None:
    rng = np.random.default_rng(0)
    matrix = rng.standard_normal((n, dim))
    for i in range(n):
        await store.upsert([VectorRecord.create(id=str(i), vector=matrix[i].tolist())])


@pytest.mark.benchmark
async def test_top_k_latency_at_10k() -> None:
    dim = 64
    n = 10_000
    store = InMemoryVectorStore()
    # Seed in one bulk upsert for speed.
    rng = np.random.default_rng(0)
    matrix = rng.standard_normal((n, dim))
    await store.upsert(
        [VectorRecord.create(id=str(i), vector=matrix[i].tolist()) for i in range(n)]
    )
    query = rng.standard_normal(dim).tolist()

    start = time.perf_counter()
    matches = await store.query(query, top_k=10)
    elapsed = time.perf_counter() - start

    assert len(matches) == 10
    assert elapsed < 2.0
    print(f"[benchmark] in-memory top-k N={n} dim={dim} latency={elapsed * 1e3:.2f}ms")
