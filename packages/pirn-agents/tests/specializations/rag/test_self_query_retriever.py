"""Tests for :class:`SelfQueryRetriever`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.retrieval.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.retrieval.vector_stores.vector_record import VectorRecord
from pirn_agents.specializations.rag.self_query_retriever import SelfQueryRetriever
from tests.specializations.conftest import StubEmbeddingProvider


def _retriever() -> SelfQueryRetriever:
    with Tapestry():
        knot = SelfQueryRetriever(
            query_spec={"query": "q", "metadata_filter": {}},
            store=InMemoryVectorStore(embedder=StubEmbeddingProvider(dimension=4)),
            embedder=StubEmbeddingProvider(dimension=4),
            _config=KnotConfig(id="retrieve"),
        )
    return knot


async def _store() -> InMemoryVectorStore:
    embedder = StubEmbeddingProvider(dimension=4)
    store = InMemoryVectorStore(embedder=embedder)
    vectors = await embedder.embed(["ho paper", "sohl paper"])
    await store.upsert(
        [
            VectorRecord.create(
                id="a", vector=vectors[0], metadata={"author": "Ho"}, document="ho paper"
            ),
            VectorRecord.create(
                id="b", vector=vectors[1], metadata={"author": "Sohl"}, document="sohl paper"
            ),
        ]
    )
    return store


class TestSelfQueryRetriever(unittest.IsolatedAsyncioTestCase):
    async def test_applies_metadata_filter(self) -> None:
        store = await _store()
        knot = _retriever()
        results = await knot.process(
            query_spec={"query": "paper", "metadata_filter": {"author": "Ho"}},
            store=store,
            embedder=StubEmbeddingProvider(dimension=4),
            top_k=5,
        )
        assert {r["id"] for r in results} == {"a"}
        assert results[0]["metadata"]["author"] == "Ho"

    async def test_no_filter_returns_all(self) -> None:
        store = await _store()
        knot = _retriever()
        results = await knot.process(
            query_spec={"query": "paper", "metadata_filter": {}},
            store=store,
            embedder=StubEmbeddingProvider(dimension=4),
            top_k=5,
        )
        assert {r["id"] for r in results} == {"a", "b"}

    async def test_rejects_non_vector_store(self) -> None:
        knot = _retriever()
        result = await knot(
            {
                "query_spec": {"query": "x", "metadata_filter": {}},
                "store": "nope",
                "embedder": StubEmbeddingProvider(dimension=4),
                "top_k": 5,
            }
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
