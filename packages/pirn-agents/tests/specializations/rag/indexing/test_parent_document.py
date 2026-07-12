"""Tests for the parent-document (small-to-big) ingest + retrieve pair."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.indexing.parent_document_ingestor import ParentDocumentIngestor
from pirn_agents.specializations.rag.indexing.parent_document_retriever import (
    ParentDocumentRetriever,
)
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from tests.specializations.conftest import StubEmbeddingProvider

_DOC = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi"


def _retriever() -> ParentDocumentRetriever:
    with Tapestry():
        knot = ParentDocumentRetriever.__new__(ParentDocumentRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="parent-retrieve"))
    return knot


class TestParentDocument(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_indexes_children_with_parent_metadata(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        with Tapestry() as t:
            ParentDocumentIngestor(
                text=_DOC,
                embedder=embedder,
                store=store,
                doc_id="d",
                child_chunk_size=10,
                group_size=2,
                _config=KnotConfig(id="ingest"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        count = result.outputs["ingest"]
        assert count > 0
        child = await store.get("d:child:0")
        assert child is not None
        assert child.metadata["parent_id"] == "d:parent:0"
        assert isinstance(child.metadata["parent_text"], str)

    async def test_retrieve_returns_parent_for_matched_child(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        with Tapestry() as t:
            ParentDocumentIngestor(
                text=_DOC,
                embedder=embedder,
                store=store,
                doc_id="d",
                child_chunk_size=10,
                group_size=2,
                _config=KnotConfig(id="ingest"),
            )
        await t.run(RunRequest())
        child = await store.get("d:child:0")
        assert child is not None and child.document is not None
        docs = await _retriever().process(
            query=child.document,
            store=store,
            embedder=StubEmbeddingProvider(dimension=4),
            top_k=2,
        )
        assert docs
        assert docs[0]["id"].startswith("d:parent:")
        # Parent text is the larger unit, not just the single child.
        assert len(docs[0]["text"]) >= len(child.document)

    async def test_retriever_rejects_non_positive_top_k(self) -> None:
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await _retriever().process(
                query="q",
                store=InMemoryVectorStore(embedder=StubEmbeddingProvider(dimension=4)),
                embedder=StubEmbeddingProvider(dimension=4),
                top_k=0,
            )
