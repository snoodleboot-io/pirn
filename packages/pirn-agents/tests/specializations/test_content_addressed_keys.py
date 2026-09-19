"""Behaviour tests: content-addressed keys are core's ``ContentHasher`` hash.

Three specializations hashed content with a bare ``hashlib.sha256(...)``
digest of their own, two of them truncated to the first 16 hex characters
(PIR-873). Truncation is a real weakening — a 64-bit prefix collides far
sooner than the full digest — and a private digest cannot be joined against
the lineage hashes the rest of pirn records.

Each test asserts the *value* of the key the knot writes, so it fails on the
old bespoke digests and passes on ``ContentHasher.hash(..., strict=True)``.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.retrieval.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.specializations.document_processing.chunk_embedder_store import (
    ChunkEmbedderStore,
)
from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.incremental.incremental_upserter import (
    IncrementalUpserter,
)
from pirn_agents.specializations.rag.indexing.raptor_assembler import RaptorAssembler
from tests.specializations.conftest import StubEmbeddingProvider, StubLLMProvider


class _DictMemoryStore(MemoryStore):
    """Dict-backed store that keeps every key written to it."""

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


class _FixedEmbedder(EmbeddingProvider):
    """Deterministic two-dimensional embedder."""

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    async def close(self) -> None:
        return None


class TestChunkEmbedderStoreKeys(unittest.IsolatedAsyncioTestCase):
    async def test_doc_id_is_the_canonical_content_hash_of_the_source(self) -> None:
        store = _DictMemoryStore()
        with Tapestry() as tapestry:
            ChunkEmbedderStore(
                chunks=["alpha", "beta"],
                source="my_doc",
                embedder=StubEmbeddingProvider(dimension=4),
                store=store,
                _config=KnotConfig(id="ces"),
            )
        result = await tapestry.run(RunRequest())
        assert result.succeeded, result.exceptions
        doc_id = ContentHasher.hash("my_doc", strict=True)
        assert sorted(store.entries) == sorted([f"{doc_id}:0", f"{doc_id}:1"])


class TestIncrementalUpserterKeys(unittest.IsolatedAsyncioTestCase):
    async def test_chunk_key_is_the_canonical_content_hash_of_the_text(self) -> None:
        store = _DictMemoryStore()
        upserter = IncrementalUpserter(store=store, embedder=_FixedEmbedder())
        chunk = Chunk(text="the only chunk", index=0, metadata={})
        plan = await upserter.upsert("doc-1", [chunk])
        content_hash = ContentHasher.hash("the only chunk", strict=True)
        assert plan.manifest_hashes == (content_hash,)
        assert f"doc-1:{content_hash}" in store.entries
        assert store.entries[f"doc-1:{content_hash}"]["chunk_hash"] == content_hash


class TestRaptorTreeKeys(unittest.IsolatedAsyncioTestCase):
    async def test_tree_content_hash_is_the_canonical_hash_of_the_leaf_chunks(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        llm = StubLLMProvider(["summary text"], repeat_last=True)
        chunks = ["alpha leaf", "beta leaf", "gamma leaf", "delta leaf"]
        with Tapestry() as tapestry:
            RaptorAssembler(
                chunks=chunks,
                llm=llm,
                embedder=embedder,
                store=store,
                cluster_size=2,
                max_levels=3,
                _config=KnotConfig(id="raptor"),
            )
        result = await tapestry.run(RunRequest())
        assert result.succeeded, result.exceptions
        tree = result.outputs["raptor"]
        assert tree.content_hash == ContentHasher.hash(chunks, strict=True)
        assert await store.get(f"raptor:{tree.content_hash}:meta") is not None


if __name__ == "__main__":
    unittest.main()
