"""Tests for incremental indexing (F25-S4): upsert-by-hash and freshness/TTL.

Uses a real dict-backed :class:`MemoryStore` (so ``retrieve`` reflects prior
writes) and a counting stub embedder to assert that only deltas are re-embedded.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.incremental.freshness_policy import (
    FreshnessPolicy,
)
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)


class _DictMemoryStore(MemoryStore):
    """Minimal dict-backed memory store for incremental-upsert assertions."""

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
    """Deterministic embedder that counts how many texts it embeds."""

    def __init__(self) -> None:
        self.embedded_texts: list[str] = []

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        self.embedded_texts.extend(texts)
        return [[float(len(t)), 1.0] for t in texts]

    async def close(self) -> None:
        return None


def _chunks(texts: Sequence[str]) -> list[Chunk]:
    return [Chunk(text=text, index=i) for i, text in enumerate(texts)]


class TestIncrementalUpserter(unittest.IsolatedAsyncioTestCase):
    async def test_first_index_embeds_all(self) -> None:
        store, embedder = _DictMemoryStore(), _CountingEmbedder()
        upserter = IncrementalUpserter(store=store, embedder=embedder, clock=lambda: 100.0)
        plan = await upserter.upsert("doc", _chunks(["a", "b", "c"]))
        assert plan.embedded_count == 3
        assert plan.unchanged_count == 0
        assert plan.removed_count == 0
        assert embedder.embedded_texts == ["a", "b", "c"]
        assert store.entries["doc:manifest"]["indexed_at"] == 100.0

    async def test_reindex_unchanged_embeds_nothing(self) -> None:
        store, embedder = _DictMemoryStore(), _CountingEmbedder()
        upserter = IncrementalUpserter(store=store, embedder=embedder, clock=lambda: 1.0)
        await upserter.upsert("doc", _chunks(["a", "b", "c"]))
        embedder.embedded_texts.clear()
        plan = await upserter.upsert("doc", _chunks(["a", "b", "c"]))
        assert plan.embedded_count == 0
        assert plan.unchanged_count == 3
        assert embedder.embedded_texts == []

    async def test_changed_chunk_reembeds_only_delta(self) -> None:
        store, embedder = _DictMemoryStore(), _CountingEmbedder()
        upserter = IncrementalUpserter(store=store, embedder=embedder)
        await upserter.upsert("doc", _chunks(["a", "b", "c"]))
        embedder.embedded_texts.clear()
        plan = await upserter.upsert("doc", _chunks(["a", "B-changed", "c"]))
        assert plan.embedded_count == 1
        assert plan.removed_count == 1  # old "b" hash removed
        assert plan.unchanged_count == 2
        assert embedder.embedded_texts == ["B-changed"]

    async def test_removed_chunk_deletes_record(self) -> None:
        store, embedder = _DictMemoryStore(), _CountingEmbedder()
        upserter = IncrementalUpserter(store=store, embedder=embedder)
        await upserter.upsert("doc", _chunks(["a", "b", "c"]))
        before_keys = {k for k in store.entries if k != "doc:manifest"}
        assert len(before_keys) == 3
        plan = await upserter.upsert("doc", _chunks(["a", "b"]))
        assert plan.removed_count == 1
        after_keys = {k for k in store.entries if k != "doc:manifest"}
        assert len(after_keys) == 2

    async def test_duplicate_content_indexed_once(self) -> None:
        store, embedder = _DictMemoryStore(), _CountingEmbedder()
        upserter = IncrementalUpserter(store=store, embedder=embedder)
        plan = await upserter.upsert("doc", _chunks(["same", "same", "other"]))
        assert plan.embedded_count == 2

    async def test_stale_and_never_indexed(self) -> None:
        store, embedder = _DictMemoryStore(), _CountingEmbedder()
        upserter = IncrementalUpserter(store=store, embedder=embedder, clock=lambda: 1000.0)
        policy = FreshnessPolicy(ttl_seconds=60.0)
        assert await upserter.is_stale("missing", policy, now=1000.0) is True
        await upserter.upsert("doc", _chunks(["a"]))
        assert await upserter.is_stale("doc", policy, now=1030.0) is False
        assert await upserter.is_stale("doc", policy, now=1100.0) is True

    def test_rejects_wrong_types(self) -> None:
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            IncrementalUpserter(store=object(), embedder=_CountingEmbedder())  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "EmbeddingProvider"):
            IncrementalUpserter(store=_DictMemoryStore(), embedder=object())  # type: ignore[arg-type]


class TestFreshnessPolicy(unittest.TestCase):
    def test_is_stale_boundary(self) -> None:
        policy = FreshnessPolicy(ttl_seconds=10.0)
        assert policy.is_stale(indexed_at=0.0, now=10.0) is False  # exactly ttl -> fresh
        assert policy.is_stale(indexed_at=0.0, now=10.1) is True
        assert policy.age_seconds(indexed_at=5.0, now=12.0) == 7.0

    def test_stale_documents_filters_and_sorts(self) -> None:
        policy = FreshnessPolicy(ttl_seconds=5.0)
        stale = policy.stale_documents({"a": 0.0, "b": 20.0, "c": 1.0}, now=10.0)
        assert stale == ["a", "c"]

    def test_invalid_ttl_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ttl_seconds"):
            FreshnessPolicy(ttl_seconds=0)


if __name__ == "__main__":
    unittest.main()
