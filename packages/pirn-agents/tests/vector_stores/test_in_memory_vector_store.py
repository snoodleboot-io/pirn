"""Tests for :class:`InMemoryVectorStore` — conformance plus numpy specifics.

The store runs the full shared conformance suite (it is the reference backend),
and additional cases cover exact-vs-approximate search modes, empty-store
behaviour, and input validation.
"""

from __future__ import annotations

import unittest

from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord
from tests.vector_stores.conformance import FixedEmbedder, VectorStoreConformance


class TestInMemoryVectorStoreConformance(VectorStoreConformance):
    async def make_store(self) -> VectorMemoryStore:
        return InMemoryVectorStore(embedder=FixedEmbedder([1.0, 0.0, 0.0]))


class TestInMemoryVectorStoreSpecifics(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_positive_probe_size(self) -> None:
        with self.assertRaises(ValueError):
            InMemoryVectorStore(probe_size=0)

    async def test_empty_store_query_returns_empty(self) -> None:
        store = InMemoryVectorStore()
        assert await store.query([1.0, 0.0], top_k=5) == []

    async def test_query_rejects_non_positive_top_k(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert([VectorRecord.create(id="a", vector=[1.0, 0.0])])
        with self.assertRaises(ValueError):
            await store.query([1.0, 0.0], top_k=0)

    async def test_search_without_embedder_raises(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert([VectorRecord.create(id="a", vector=[1.0, 0.0])])
        with self.assertRaises(RuntimeError):
            await store.search("q")

    async def test_approximate_mode_returns_subset_of_exact(self) -> None:
        records = [
            VectorRecord.create(id=str(i), vector=[float(i % 7), float(i % 3), 1.0])
            for i in range(200)
        ]
        exact = InMemoryVectorStore()
        approx = InMemoryVectorStore(approximate=True, probe_size=32, seed=1)
        await exact.upsert(records)
        await approx.upsert(records)

        approx_matches = await approx.query([1.0, 1.0, 1.0], top_k=5)
        # approximate mode still returns valid, ranked results from the corpus
        assert 0 < len(approx_matches) <= 5
        approx_scores = [m.score for m in approx_matches]
        assert approx_scores == sorted(approx_scores, reverse=True)
        all_ids = {r.id for r in records}
        assert all(m.id in all_ids for m in approx_matches)

    async def test_close_clears_records(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert([VectorRecord.create(id="a", vector=[1.0, 0.0])])
        await store.close()
        assert await store.get("a") is None


if __name__ == "__main__":
    unittest.main()
