"""Tests for the sentence-window ingest + retrieve pair."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.indexing.sentence_window_ingestor import SentenceWindowIngestor
from pirn_agents.specializations.rag.indexing.sentence_window_retriever import (
    SentenceWindowRetriever,
)
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from tests.specializations.conftest import StubEmbeddingProvider

_DOC = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."


def _ingestor() -> SentenceWindowIngestor:
    with Tapestry():
        knot = SentenceWindowIngestor.__new__(SentenceWindowIngestor)
        object.__setattr__(knot, "_config", KnotConfig(id="sw-ingest"))
    return knot


def _retriever() -> SentenceWindowRetriever:
    with Tapestry():
        knot = SentenceWindowRetriever.__new__(SentenceWindowRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="sw-retrieve"))
    return knot


class TestSentenceWindow(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_stores_windows(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        count = await _ingestor().process(
            text=_DOC, embedder=embedder, store=store, doc_id="d", window_size=1
        )
        assert count == 4
        second = await store.get("d:sent:1")
        assert second is not None
        # Window around sentence 1 includes sentences 0, 1, 2.
        assert "First sentence" in second.metadata["window"]
        assert "Third sentence" in second.metadata["window"]

    async def test_retrieve_returns_window_around_match(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        await _ingestor().process(
            text=_DOC, embedder=embedder, store=store, doc_id="d", window_size=1
        )
        results = await _retriever().process(
            query="Second sentence here.",
            store=store,
            embedder=StubEmbeddingProvider(dimension=4),
            top_k=1,
        )
        assert results
        assert results[0]["sentence"] == "Second sentence here."
        # The returned text is the wider window, not just the sentence.
        assert len(results[0]["text"]) > len(results[0]["sentence"])

    async def test_ingest_rejects_negative_window(self) -> None:
        with self.assertRaisesRegex(ValueError, "window_size must be a non-negative int"):
            await _ingestor().process(
                text=_DOC,
                embedder=StubEmbeddingProvider(dimension=4),
                store=InMemoryVectorStore(embedder=StubEmbeddingProvider(dimension=4)),
                doc_id="d",
                window_size=-1,
            )
