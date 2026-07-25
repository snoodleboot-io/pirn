"""Incremental re-index cost benchmark (F25-S4-T3 / PIR-631).

Indexes a large corpus once, then re-indexes it with only a small fraction of
chunks changed, and asserts the re-embed count equals the change volume — not
the corpus size — so incremental cost is decoupled from corpus size.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import pytest

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from tests.benchmarks.conftest import BenchmarkRecorder


class _DictMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.entries: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.entries[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.entries.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for entry in list(self.entries.values())[:top_k]:
                yield entry

        return _aiter()

    async def forget(self, key: str) -> None:
        self.entries.pop(key, None)

    async def close(self) -> None:
        return None


class _CountingEmbedder(EmbeddingProvider):
    def __init__(self) -> None:
        self.count = 0

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        self.count += len(texts)
        return [[1.0, 0.0] for _ in texts]

    async def close(self) -> None:
        return None


def _chunks(texts: Sequence[str]) -> list[Chunk]:
    return [Chunk(text=text, index=i) for i, text in enumerate(texts)]


@pytest.mark.benchmark
async def test_reindex_cost_scales_with_change_volume(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    corpus_size = 500
    changed = 10
    store, embedder = _DictMemoryStore(), _CountingEmbedder()
    upserter = IncrementalUpserter(store=store, embedder=embedder)

    original = [f"chunk-{i}" for i in range(corpus_size)]
    start = time.perf_counter()
    await upserter.upsert("doc", _chunks(original))
    full_seconds = time.perf_counter() - start
    assert embedder.count == corpus_size

    embedder.count = 0
    updated = list(original)
    for i in range(changed):
        updated[i] = f"chunk-{i}-v2"
    start = time.perf_counter()
    plan = await upserter.upsert("doc", _chunks(updated))
    delta_seconds = time.perf_counter() - start

    # Only the changed chunks are re-embedded — cost tracks change volume.
    assert embedder.count == changed
    assert plan.embedded_count == changed
    assert plan.unchanged_count == corpus_size - changed
    assert plan.removed_count == changed

    benchmark_recorder.record(
        "IncrementalReindex",
        corpus=float(corpus_size),
        changed=float(changed),
        full_seconds=full_seconds,
        delta_seconds=delta_seconds,
        reembedded=float(embedder.count),
    )


if __name__ == "__main__":
    import unittest

    unittest.main()
