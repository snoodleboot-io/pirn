"""Unit tests for :class:`EmbeddingIndexer`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.document_processing.embedding_indexer import (
    EmbeddingIndexer,
)
from tests.specializations.conftest import (
    StubEmbeddingProvider,
    StubMemoryStore,
)


class _DictMemoryStore(MemoryStore):
    """A store that keeps every record, so an overwrite is observable."""

    def __init__(self) -> None:
        self.entries: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.entries[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.entries.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> Sequence[Mapping[str, Any]]:
        return list(self.entries.values())[:top_k]

    async def forget(self, key: str) -> None:
        self.entries.pop(key, None)

    async def close(self) -> None:
        return None


def _make_knot(embedder: StubEmbeddingProvider, store: MemoryStore) -> EmbeddingIndexer:
    with Tapestry():
        return EmbeddingIndexer(
            chunks=[],
            document_id="doc",
            embedding_provider=embedder,
            store=store,
            _config=KnotConfig(id="ei"),
        )


class TestEmbeddingIndexerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_zero(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        result = await k.process(
            chunks=[], document_id="doc", embedding_provider=embedder, store=store
        )
        assert result == 0

    async def test_returns_count_of_indexed_chunks(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        result = await k.process(
            chunks=["a", "b", "c"], document_id="doc", embedding_provider=embedder, store=store
        )
        assert result == 3

    async def test_raises_for_non_string_chunk(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        k = _make_knot(embedder, store)
        with self.assertRaises(TypeError):
            await k.process(
                chunks=["ok", 42],  # type: ignore[list-item]
                document_id="doc",
                embedding_provider=embedder,
                store=store,
            )

    async def test_rejects_empty_document_id(self) -> None:
        embedder = StubEmbeddingProvider()
        store = _DictMemoryStore()
        k = _make_knot(embedder, store)
        with self.assertRaises(ValueError):
            await k.process(chunks=["x"], document_id="", embedding_provider=embedder, store=store)
        assert store.entries == {}


class TestEmbeddingIndexerDocumentScope(unittest.IsolatedAsyncioTestCase):
    async def test_second_document_does_not_overwrite_first(self) -> None:
        """Two documents with the same chunk count indexed into one store both survive."""
        embedder = StubEmbeddingProvider()
        store = _DictMemoryStore()
        with Tapestry() as t:
            EmbeddingIndexer(
                chunks=["a0", "a1"],
                document_id="doc-a",
                embedding_provider=embedder,
                store=store,
                _config=KnotConfig(id="index_a"),
            )
        with Tapestry() as t2:
            EmbeddingIndexer(
                chunks=["b0", "b1"],
                document_id="doc-b",
                embedding_provider=embedder,
                store=store,
                _config=KnotConfig(id="index_b"),
            )
        first = await t.run(RunRequest())
        second = await t2.run(RunRequest())
        assert first.succeeded, first.exceptions
        assert second.succeeded, second.exceptions

        texts = sorted(str(entry["text"]) for entry in store.entries.values())
        assert texts == ["a0", "a1", "b0", "b1"]
        assert store.entries["doc-a:1"]["text"] == "a1"
        assert store.entries["doc-b:0"]["doc_id"] == "doc-b"
        assert store.entries["doc-b:0"]["chunk_index"] == 0
