"""Unit tests for :class:`_ChunkEmbedderStore`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.document_processing._chunk_embedder_store import (
    _ChunkEmbedderStore,
)
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.specializations.conftest import (
    StubEmbeddingProvider,
    StubMemoryStore,
)


def _make_knot(embedder: StubEmbeddingProvider, store: StubMemoryStore) -> _ChunkEmbedderStore:
    with Tapestry():
        return _ChunkEmbedderStore(
            chunks=[],
            source="doc.txt",
            embedder=embedder,
            store=store,
            _config=KnotConfig(id="ces"),
        )


class TestChunkEmbedderStoreProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_zero(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        result = await k.process(chunks=[], source="x", embedder=embedder, store=store)
        assert result == 0

    async def test_stores_correct_count(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        result = await k.process(chunks=["alpha", "beta"], source="doc.txt", embedder=embedder, store=store)
        assert result == 2

    async def test_keys_follow_doc_id_pattern(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        stored_keys: list[str] = []
        store = StubMemoryStore(hits=[])
        original_store = store.store

        async def _capture(key, value):
            stored_keys.append(key)
            return await original_store(key, value)

        store.store = _capture  # type: ignore[assignment]
        k = _make_knot(embedder, store)
        await k.process(chunks=["hello"], source="my_doc", embedder=embedder, store=store)
        assert ":" in stored_keys[0]

    async def test_payload_contains_text_and_embedding(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        stored_payloads: list[dict] = []
        store = StubMemoryStore(hits=[])
        original_store = store.store

        async def _capture(key, value):
            stored_payloads.append(dict(value))
            return await original_store(key, value)

        store.store = _capture  # type: ignore[assignment]
        k = _make_knot(embedder, store)
        await k.process(chunks=["chunk_text"], source="doc", embedder=embedder, store=store)
        assert stored_payloads[0]["text"] == "chunk_text"
        assert "embedding" in stored_payloads[0]

    async def test_raises_when_embedder_returns_wrong_count(self) -> None:
        class MismatchEmbedder(StubEmbeddingProvider):
            async def embed(self, texts, *, model=None):
                return []  # always returns 0 vectors

        store = StubMemoryStore(hits=[])
        embedder = MismatchEmbedder()
        k = _make_knot(embedder, store)
        with self.assertRaises(RuntimeError):
            await k.process(chunks=["a", "b"], source="x", embedder=embedder, store=store)
