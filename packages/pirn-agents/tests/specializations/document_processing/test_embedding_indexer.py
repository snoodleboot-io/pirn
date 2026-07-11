"""Unit tests for :class:`EmbeddingIndexer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing.embedding_indexer import (
    EmbeddingIndexer,
)
from tests.specializations.conftest import (
    StubEmbeddingProvider,
    StubMemoryStore,
)


def _make_knot(embedder: StubEmbeddingProvider, store: StubMemoryStore) -> EmbeddingIndexer:
    with Tapestry():
        return EmbeddingIndexer(
            chunks=[],
            embedding_provider=embedder,
            store=store,
            _config=KnotConfig(id="ei"),
        )


class TestEmbeddingIndexerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_zero(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        result = await k.process(chunks=[], embedding_provider=embedder, store=store)
        assert result == 0

    async def test_returns_count_of_indexed_chunks(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        result = await k.process(chunks=["a", "b", "c"], embedding_provider=embedder, store=store)
        assert result == 3

    async def test_raises_for_non_string_chunk(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        with self.assertRaises(TypeError):
            await k.process(
                chunks=["ok", 42],  # type: ignore[list-item]
                embedding_provider=embedder,
                store=store,
            )
