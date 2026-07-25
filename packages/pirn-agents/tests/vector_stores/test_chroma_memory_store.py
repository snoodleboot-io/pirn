"""Tests for :class:`ChromaMemoryStore`.

The full shared conformance suite runs against the adapter wired to an in-memory
neutral backend fake (no ``chromadb`` imported). A ``needs_chroma`` case runs the
same intent against a real Chroma when installed, and a guard proves importing
the store leaves the backend unimported.
"""

from __future__ import annotations

import sys
import unittest

import pytest

from pirn_agents.vector_stores.chroma_memory_store import ChromaMemoryStore
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from tests.vector_stores.conformance import (
    FakeVectorBackendClient,
    FixedEmbedder,
    VectorStoreConformance,
)


class TestChromaConformance(VectorStoreConformance):
    async def make_store(self) -> VectorMemoryStore:
        return ChromaMemoryStore(
            collection="conf",
            embedder=FixedEmbedder([1.0, 0.0, 0.0]),
            client=FakeVectorBackendClient(),
        )


class TestChromaStoreSpecifics(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_positive_batch_size(self) -> None:
        with self.assertRaises(ValueError):
            ChromaMemoryStore(collection="c", batch_size=-1)

    async def test_close_closes_backend_client(self) -> None:
        client = FakeVectorBackendClient()
        store = ChromaMemoryStore(collection="c", client=client)
        await store.close()
        assert client.closed is True

    def test_import_does_not_pull_backend(self) -> None:
        assert "chromadb" not in sys.modules


@pytest.mark.needs_chroma
class TestChromaRealBackend(unittest.IsolatedAsyncioTestCase):
    async def test_conformance_against_real_chroma(self) -> None:
        pytest.importorskip("chromadb")
        from pirn_agents.vector_stores.vector_record import VectorRecord

        store = ChromaMemoryStore(collection="pirn_conf")
        await store.upsert([VectorRecord.create(id="a", vector=[1.0, 0.0, 0.0])])
        matches = await store.query([1.0, 0.0, 0.0], top_k=1)
        assert matches and matches[0].id == "a"
        await store.close()


if __name__ == "__main__":
    unittest.main()
