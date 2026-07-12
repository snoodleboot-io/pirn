"""Tests for the auto-merging ingest + retrieve pair."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.indexing.auto_merging_ingestor import AutoMergingIngestor
from pirn_agents.specializations.rag.indexing.auto_merging_retriever import AutoMergingRetriever
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from tests.specializations.conftest import StubEmbeddingProvider

_DOC = "aaaaaaaa bbbbbbbb cccccccc dddddddd"


def _retriever() -> AutoMergingRetriever:
    with Tapestry():
        knot = AutoMergingRetriever.__new__(AutoMergingRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="am-retrieve"))
    return knot


async def _ingest() -> tuple[InMemoryVectorStore, StubEmbeddingProvider]:
    embedder = StubEmbeddingProvider(dimension=4)
    store = InMemoryVectorStore(embedder=embedder)
    with Tapestry() as t:
        AutoMergingIngestor(
            text=_DOC,
            embedder=embedder,
            store=store,
            doc_id="d",
            leaf_chunk_size=8,
            chunk_overlap=0,
            group_size=4,
            _config=KnotConfig(id="ingest"),
        )
    await t.run(RunRequest())
    return store, embedder


class TestAutoMerging(unittest.IsolatedAsyncioTestCase):
    async def test_merges_to_parent_when_many_leaves_retrieved(self) -> None:
        store, _ = await _ingest()
        leaf = await store.get("d:child:0")
        assert leaf is not None and leaf.document is not None
        # Over-fetch pulls all leaves of the single parent -> merge.
        docs = await _retriever().process(
            query=leaf.document,
            store=store,
            embedder=StubEmbeddingProvider(dimension=4),
            top_k=5,
            candidate_multiplier=4,
            merge_threshold=0.5,
        )
        assert docs
        assert docs[0]["merged"] is True
        assert docs[0]["id"].startswith("d:parent:")

    async def test_keeps_leaves_when_below_threshold(self) -> None:
        store, _ = await _ingest()
        leaf = await store.get("d:child:0")
        assert leaf is not None and leaf.document is not None
        # Fetch only a single leaf -> ratio below threshold -> no merge.
        docs = await _retriever().process(
            query=leaf.document,
            store=store,
            embedder=StubEmbeddingProvider(dimension=4),
            top_k=1,
            candidate_multiplier=1,
            merge_threshold=0.5,
        )
        assert docs
        assert docs[0]["merged"] is False
        assert docs[0]["id"].startswith("d:child:")

    async def test_rejects_bad_merge_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "merge_threshold must be in"):
            await _retriever().process(
                query="q",
                store=InMemoryVectorStore(embedder=StubEmbeddingProvider(dimension=4)),
                embedder=StubEmbeddingProvider(dimension=4),
                merge_threshold=0.0,
            )
