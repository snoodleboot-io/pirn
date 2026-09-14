"""Unit tests for :class:`_ChunkEmbedderStore`.

PIR-867: each chunk's persisted write is independent of every other chunk's,
so ``_ChunkEmbedderStore`` fans them out (one ``_ChunkStoreWrite`` knot per
chunk wired into an ``Aggregator``) rather than awaiting ``store.store`` under
a hand-rolled ``asyncio.gather``. ``process`` therefore returns the sink of an
inner pipeline instead of the stored count directly, so the outcome tests run
a real tapestry and read the knot's output (the pattern PIR-856 established
for ``ParallelToolCaller``). The embedding call stays a single batch call, so
``test_raises_when_embedder_returns_wrong_count`` still exercises ``process``
directly — the guard fires before any per-chunk knot is built.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._chunk_embedder_store import (
    _ChunkEmbedderStore,
)
from tests.specializations.conftest import (
    StubEmbeddingProvider,
    StubMemoryStore,
)


def _make_knot(embedder: StubEmbeddingProvider, store: StubMemoryStore) -> _ChunkEmbedderStore:
    with Tapestry():
        return _ChunkEmbedderStore(
            chunks=[],
            source="doc.txt",
            embedder=embedder,
            store=store,
            _config=KnotConfig(id="ces"),
        )


def _run(embedder, store, chunks: list[str], source: str) -> Tapestry:
    with Tapestry() as t:
        _ChunkEmbedderStore(
            chunks=chunks,
            source=source,
            embedder=embedder,
            store=store,
            _config=KnotConfig(id="ces"),
        )
    return t


class TestChunkEmbedderStoreProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_zero(self) -> None:
        embedder = StubEmbeddingProvider()
        store = StubMemoryStore(hits=[])
        t = _run(embedder, store, [], "x")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["ces"] == 0

    async def test_stores_correct_count(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = StubMemoryStore(hits=[])
        t = _run(embedder, store, ["alpha", "beta"], "doc.txt")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["ces"] == 2

    async def test_keys_follow_doc_id_pattern(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        stored_keys: list[str] = []
        store = StubMemoryStore(hits=[])
        original_store = store.store

        async def _capture(key, value):
            stored_keys.append(key)
            return await original_store(key, value)

        store.store = _capture  # type: ignore[assignment]
        t = _run(embedder, store, ["hello"], "my_doc")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert ":" in stored_keys[0]

    async def test_payload_contains_text_and_embedding(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        stored_payloads: list[dict] = []
        store = StubMemoryStore(hits=[])
        original_store = store.store

        async def _capture(key, value):
            stored_payloads.append(dict(value))
            return await original_store(key, value)

        store.store = _capture  # type: ignore[assignment]
        t = _run(embedder, store, ["chunk_text"], "doc")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert stored_payloads[0]["text"] == "chunk_text"
        assert "embedding" in stored_payloads[0]

    async def test_raises_when_embedder_returns_wrong_count(self) -> None:
        class MismatchEmbedder(StubEmbeddingProvider):
            async def embed(self, texts, *, model=None):
                return []  # always returns 0 vectors

        store = StubMemoryStore(hits=[])
        embedder = MismatchEmbedder()
        k = _make_knot(embedder, store)
        with self.assertRaises(RuntimeError):
            await k.process(chunks=["a", "b"], source="x", embedder=embedder, store=store)

    async def test_each_chunk_gets_its_own_lineage_row(self) -> None:
        """PIR-867: each chunk is a node now, not both under one asyncio.gather."""
        embedder = StubEmbeddingProvider(dimension=4)
        store = StubMemoryStore(hits=[])
        t = _run(embedder, store, ["a", "b"], "doc.txt")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        children = await t.history.children_of(result.run_id)
        inner_knot_ids = {row.knot_id for child in children for row in child.lineage}
        assert {"write_0", "write_1"} <= inner_knot_ids, inner_knot_ids


if __name__ == "__main__":
    unittest.main()
