"""Micro-benchmark: embedding throughput vs. batch size (PAE-F4-S1-T4).

Validates the batching-by-default performance claim: a larger batch size turns a
fixed workload into fewer backend round-trips. Wall-clock is measured directly;
the primary assertion is on round-trip count (deterministic and non-flaky), with
timings printed for an F10-style report to harvest.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import pytest

from pirn_agents.embeddings.base_embedding_provider import BaseEmbeddingProvider


class CountingProvider(BaseEmbeddingProvider):
    """Counts backend round-trips; each batch costs a fixed tiny latency."""

    def __init__(self, *, latency: float, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.round_trips = 0
        self._latency = latency

    async def _create_client(self) -> Any:
        return object()

    async def _embed_batch(self, texts: Sequence[str], model: str | None) -> list[list[float]]:
        self.round_trips += 1
        time.sleep(self._latency)
        return [[float(len(text))] for text in texts]


@pytest.mark.benchmark
async def test_larger_batch_size_means_fewer_round_trips() -> None:
    workload = [f"doc-{i}" for i in range(64)]
    latency = 0.001
    figures: list[tuple[int, int, float]] = []

    for batch_size in (1, 8, 64):
        provider = CountingProvider(latency=latency, batch_size=batch_size)
        start = time.perf_counter()
        await provider.embed(workload)
        elapsed = time.perf_counter() - start
        figures.append((batch_size, provider.round_trips, elapsed))

    round_trips = {bs: rt for bs, rt, _ in figures}
    assert round_trips[1] == 64
    assert round_trips[8] == 8
    assert round_trips[64] == 1
    # strictly decreasing round-trips as batch size grows
    assert round_trips[1] > round_trips[8] > round_trips[64]

    for batch_size, trips, elapsed in figures:
        print(
            f"[benchmark] embed N={len(workload)} batch_size={batch_size} "
            f"round_trips={trips} elapsed={elapsed:.4f}s"
        )
