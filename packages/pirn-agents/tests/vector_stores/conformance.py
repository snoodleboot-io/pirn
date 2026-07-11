"""Shared ``MemoryStore`` conformance suite reused by every vector store.

``VectorStoreConformance`` is a mixin of async test methods that exercise the
whole :class:`VectorMemoryStore` contract — vector-native ``upsert``/``query``/
``get``/``delete`` plus the keyed ``store``/``retrieve``/``search``/``forget``
surface — against whatever store ``make_store`` returns. The in-memory reference,
and the pgvector/Qdrant/Chroma adapters (behind in-memory fakes), all subclass
it, so one suite guarantees behavioural parity across backends.

The class is intentionally NOT named ``Test*`` so pytest does not collect the
abstract base directly; concrete ``Test*`` subclasses inherit its cases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.vector_stores.metadata_match import matches_metadata_filter
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class FixedEmbedder(EmbeddingProvider):
    """Embeds every text to the same fixed vector (deterministic search)."""

    def __init__(self, vector: Sequence[float]) -> None:
        self._vector = [float(x) for x in vector]

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        return [list(self._vector) for _ in texts]

    async def close(self) -> None:
        return None


class FakeVectorBackendClient:
    """In-memory neutral backend client: cosine search + metadata filtering.

    Faithful enough to run the whole conformance suite against the Qdrant and
    Chroma adapters with no backend installed, isolating adapter wiring from
    vendor SDK translation (which is covered separately behind ``needs_*``).
    """

    def __init__(self) -> None:
        self._points: dict[str, dict[str, Any]] = {}
        self.closed = False

    async def upsert_points(self, points: Sequence[Mapping[str, Any]]) -> None:
        for point in points:
            self._points[point["id"]] = {
                "id": point["id"],
                "vector": [float(x) for x in point["vector"]],
                "metadata": dict(point.get("metadata", {})),
                "document": point.get("document"),
            }

    async def search_points(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        metadata_filter: Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]]:
        query = np.asarray(vector, dtype=np.float64)
        query_norm = float(np.linalg.norm(query)) or 1.0
        scored: list[tuple[float, dict[str, Any]]] = []
        for point in self._points.values():
            if not matches_metadata_filter(point["metadata"], metadata_filter):
                continue
            candidate = np.asarray(point["vector"], dtype=np.float64)
            denom = (float(np.linalg.norm(candidate)) or 1.0) * query_norm
            score = float(candidate @ query) / denom
            scored.append((score, point))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {
                "id": point["id"],
                "score": score,
                "metadata": dict(point["metadata"]),
                "document": point["document"],
            }
            for score, point in scored[:top_k]
        ]

    async def get_point(self, key: str) -> Mapping[str, Any] | None:
        point = self._points.get(key)
        if point is None:
            return None
        return dict(point)

    async def delete_points(self, ids: Sequence[str]) -> None:
        for key in ids:
            self._points.pop(key, None)

    async def close(self) -> None:
        self.closed = True


class VectorStoreConformance:
    """Reusable async conformance cases for any :class:`VectorMemoryStore`."""

    async def make_store(self) -> VectorMemoryStore:
        """Return a fresh, empty store configured with a ``FixedEmbedder([1,0,0])``."""
        raise NotImplementedError

    @staticmethod
    def _corpus() -> list[VectorRecord]:
        """Return the shared 3-record fixture used by every case."""
        return [
            VectorRecord.create(
                id="a", vector=[1.0, 0.0, 0.0], metadata={"kind": "x"}, document="alpha"
            ),
            VectorRecord.create(
                id="b", vector=[0.0, 1.0, 0.0], metadata={"kind": "y"}, document="beta"
            ),
            VectorRecord.create(
                id="c", vector=[0.9, 0.1, 0.0], metadata={"kind": "x"}, document="gamma"
            ),
        ]

    async def _seeded(self) -> VectorMemoryStore:
        store = await self.make_store()
        await store.upsert(self._corpus())
        return store

    async def test_upsert_and_get_roundtrip(self) -> None:
        store = await self._seeded()
        record = await store.get("a")
        assert record is not None
        assert record.id == "a"
        assert record.metadata["kind"] == "x"
        assert record.document == "alpha"
        np_vec = np.asarray(record.vector, dtype=float)
        assert np.allclose(np_vec, [1.0, 0.0, 0.0], atol=1e-6)

    async def test_get_missing_returns_none(self) -> None:
        store = await self._seeded()
        assert await store.get("does-not-exist") is None

    async def test_query_orders_by_cosine_similarity(self) -> None:
        store = await self._seeded()
        matches = await store.query([1.0, 0.0, 0.0], top_k=3)
        assert [m.id for m in matches][:2] == ["a", "c"]
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)

    async def test_query_respects_top_k(self) -> None:
        store = await self._seeded()
        matches = await store.query([1.0, 0.0, 0.0], top_k=1)
        assert len(matches) == 1
        assert matches[0].id == "a"

    async def test_query_metadata_filter(self) -> None:
        store = await self._seeded()
        matches = await store.query([1.0, 0.0, 0.0], top_k=3, metadata_filter={"kind": "x"})
        ids = {m.id for m in matches}
        assert ids == {"a", "c"}
        assert "b" not in ids

    async def test_delete_removes_record(self) -> None:
        store = await self._seeded()
        await store.delete(["a"])
        assert await store.get("a") is None
        matches = await store.query([1.0, 0.0, 0.0], top_k=3)
        assert "a" not in {m.id for m in matches}

    async def test_upsert_overwrites_existing_id(self) -> None:
        store = await self._seeded()
        await store.upsert(
            [VectorRecord.create(id="a", vector=[0.0, 0.0, 1.0], metadata={"kind": "z"})]
        )
        record = await store.get("a")
        assert record is not None
        assert record.metadata["kind"] == "z"
        assert np.allclose(np.asarray(record.vector, dtype=float), [0.0, 0.0, 1.0], atol=1e-6)

    async def test_keyed_store_and_retrieve(self) -> None:
        store = await self.make_store()
        await store.store(
            "d", {"vector": [0.0, 0.0, 1.0], "metadata": {"kind": "z"}, "document": "delta"}
        )
        retrieved = await store.retrieve("d")
        assert retrieved is not None
        assert retrieved["metadata"]["kind"] == "z"
        assert retrieved["document"] == "delta"

    async def test_forget_via_keyed_surface(self) -> None:
        store = await self._seeded()
        await store.forget("a")
        assert await store.retrieve("a") is None

    async def test_search_uses_embedder(self) -> None:
        store = await self._seeded()
        hits: list[Mapping[str, Any]] = []
        async for hit in await store.search("anything", top_k=2):
            hits.append(hit)
        assert len(hits) == 2
        assert hits[0]["id"] == "a"
