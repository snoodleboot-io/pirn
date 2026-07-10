"""Tests for :class:`QdrantMemoryStore`.

The full shared conformance suite runs against the adapter wired to an in-memory
neutral backend fake (no ``qdrant_client`` imported). A ``needs_qdrant`` case
runs the same intent against a real Qdrant when configured, and a guard proves
importing the store leaves the backend unimported.
"""

from __future__ import annotations

import os
import sys
import unittest

import pytest

from pirn_agents.vector_stores.qdrant_memory_store import QdrantMemoryStore
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from tests.vector_stores.conformance import (
    FakeVectorBackendClient,
    FixedEmbedder,
    VectorStoreConformance,
)


class TestQdrantConformance(VectorStoreConformance):
    async def make_store(self) -> VectorMemoryStore:
        return QdrantMemoryStore(
            collection="conf",
            dimension=3,
            embedder=FixedEmbedder([1.0, 0.0, 0.0]),
            client=FakeVectorBackendClient(),
        )


class TestQdrantStoreSpecifics(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_positive_batch_size(self) -> None:
        with self.assertRaises(ValueError):
            QdrantMemoryStore(collection="c", dimension=3, batch_size=0)

    async def test_close_closes_backend_client(self) -> None:
        client = FakeVectorBackendClient()
        store = QdrantMemoryStore(collection="c", dimension=3, client=client)
        await store.close()
        assert client.closed is True

    def test_import_does_not_pull_backend(self) -> None:
        assert "qdrant_client" not in sys.modules


@pytest.mark.needs_qdrant
class TestQdrantRealBackend(unittest.IsolatedAsyncioTestCase):
    async def test_conformance_against_real_qdrant(self) -> None:
        url = os.environ.get("PIRN_TEST_QDRANT_URL")
        if not url:
            self.skipTest("PIRN_TEST_QDRANT_URL not set")
        from pirn_agents.vector_stores.vector_record import VectorRecord

        store = QdrantMemoryStore(collection="pirn_conf", dimension=3, url=url)
        await store.upsert([VectorRecord.create(id="a", vector=[1.0, 0.0, 0.0])])
        matches = await store.query([1.0, 0.0, 0.0], top_k=1)
        assert matches and matches[0].id == "a"
        await store.close()


if __name__ == "__main__":
    unittest.main()
