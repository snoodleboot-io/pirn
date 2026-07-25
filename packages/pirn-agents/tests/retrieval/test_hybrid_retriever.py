"""Tests for the :class:`HybridRetriever` knot (concurrent dense + BM25 + RRF)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.retrieval.bm25_index import Bm25Index
from pirn_agents.retrieval.hybrid_retriever import HybridRetriever
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.vector_stores.vector_record import VectorRecord
from tests.vector_stores.conformance import FixedEmbedder


def _make_retriever() -> HybridRetriever:
    with Tapestry():
        knot = HybridRetriever.__new__(HybridRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="hybrid"))
    return knot


async def _make_store() -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    await store.upsert(
        [
            VectorRecord.create(id="dense-1", vector=[1.0, 0.0], document="alpha alpha"),
            VectorRecord.create(id="dense-2", vector=[0.9, 0.1], document="beta"),
            VectorRecord.create(id="lex-1", vector=[0.0, 1.0], document="rareword gamma"),
        ]
    )
    return store


def _make_bm25() -> Bm25Index:
    index = Bm25Index()
    index.add("dense-1", "alpha alpha")
    index.add("dense-2", "beta")
    index.add("lex-1", "rareword gamma")
    return index


class TestHybridRetriever(unittest.IsolatedAsyncioTestCase):
    async def test_fuses_dense_and_lexical_results(self) -> None:
        store = await _make_store()
        retriever = _make_retriever()

        results = await retriever.process(
            query="rareword",
            store=store,
            lexical=_make_bm25(),
            embedder=FixedEmbedder([1.0, 0.0]),
            top_k=3,
        )

        ids = [hit["id"] for hit in results]
        # dense arm (query vector [1,0]) surfaces dense-1/dense-2; lexical arm
        # surfaces lex-1 via the rare keyword -> fusion contains both arms.
        assert "lex-1" in ids
        assert "dense-1" in ids
        scores = [hit["score"] for hit in results]
        assert scores == sorted(scores, reverse=True)

    async def test_respects_top_k(self) -> None:
        store = await _make_store()
        retriever = _make_retriever()
        results = await retriever.process(
            query="alpha",
            store=store,
            lexical=_make_bm25(),
            embedder=FixedEmbedder([1.0, 0.0]),
            top_k=1,
        )
        assert len(results) == 1

    async def test_rejects_bad_types(self) -> None:
        retriever = _make_retriever()
        with self.assertRaisesRegex(TypeError, "store must be a VectorMemoryStore"):
            await retriever.process(
                query="q",
                store="not-a-store",  # type: ignore[arg-type]
                lexical=_make_bm25(),
                embedder=FixedEmbedder([1.0, 0.0]),
            )

    async def test_rejects_non_positive_top_k(self) -> None:
        store = await _make_store()
        retriever = _make_retriever()
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await retriever.process(
                query="q",
                store=store,
                lexical=_make_bm25(),
                embedder=FixedEmbedder([1.0, 0.0]),
                top_k=0,
            )

    async def test_constructs_and_runs_through_tapestry(self) -> None:
        store = await _make_store()
        with Tapestry() as tapestry:
            HybridRetriever(
                query="rareword",
                store=store,
                lexical=_make_bm25(),
                embedder=FixedEmbedder([1.0, 0.0]),
                top_k=2,
                _config=KnotConfig(id="hybrid"),
            )
        result = await tapestry.run(RunRequest())
        assert result.succeeded
        ids = [hit["id"] for hit in result.outputs["hybrid"]]
        assert "lex-1" in ids


if __name__ == "__main__":
    unittest.main()
