"""``ChromaMemoryStore`` — a Chroma-backed :class:`VectorMemoryStore`.

Adapts the neutral vector-store contract onto Chroma. As with the Qdrant
adapter, all vendor specifics live behind a
:class:`~pirn_agents.vector_stores.vector_backend_client.VectorBackendClient`:
by default the store lazily builds a
:class:`~pirn_agents.vector_stores.chroma_backend_client.ChromaBackendClient`
(which imports ``chromadb`` behind the ``[chroma]`` extra and thread-offloads its
synchronous calls), but a client may be injected so mirrored tests run the full
conformance suite against an in-memory fake with no backend installed. Upserts
are batched.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from pirn_agents.credential_ref import CredentialRef
from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.vector_stores.vector_backend_client import VectorBackendClient
from pirn_agents.vector_stores.vector_match import VectorMatch
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class ChromaMemoryStore(VectorMemoryStore):
    """A Chroma :class:`VectorMemoryStore` speaking the neutral backend client."""

    def __init__(
        self,
        *,
        collection: str,
        embedder: EmbeddingProvider | None = None,
        persist_path: str | None = None,
        batch_size: int = 128,
        credential: CredentialRef | None = None,
        client: VectorBackendClient | None = None,
    ) -> None:
        """Initialise the Chroma adapter.

        Args:
            collection: Target Chroma collection name.
            embedder: Optional provider enabling text :meth:`search`.
            persist_path: Optional on-disk path for a persistent client.
            batch_size: Points per upsert batch. Must be positive.
            credential: Optional credential scrubbed on :meth:`close`.
            client: Optional pre-built neutral backend client (the test seam);
                when supplied no backend import happens.

        Raises:
            ValueError: If ``batch_size`` is not a positive int.
        """
        super().__init__(embedder=embedder)
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError(f"batch_size must be a positive int, got {batch_size!r}")
        self._collection: str = collection
        self._persist_path: str | None = persist_path
        self._batch_size: int = batch_size
        self._credential: CredentialRef | None = credential
        self._client: VectorBackendClient | None = client

    async def _get_client(self) -> VectorBackendClient:
        """Return the backend client, lazily building the real one once."""
        if self._client is None:
            from pirn_agents.vector_stores.chroma_backend_client import (
                ChromaBackendClient,
            )

            self._client = ChromaBackendClient(
                collection=self._collection,
                persist_path=self._persist_path,
            )
        return self._client

    def _iter_batches(self, points: list[Mapping[str, Any]]) -> Iterator[list[Mapping[str, Any]]]:
        """Yield ``points`` in contiguous chunks of at most ``batch_size``."""
        for start in range(0, len(points), self._batch_size):
            yield points[start : start + self._batch_size]

    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Batch-upsert ``records`` through the neutral backend client."""
        points: list[Mapping[str, Any]] = [
            {
                "id": record.id,
                "vector": list(record.vector),
                "metadata": dict(record.metadata),
                "document": record.document,
            }
            for record in records
        ]
        if not points:
            return
        client = await self._get_client()
        for batch in self._iter_batches(points):
            await client.upsert_points(batch)

    async def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Return up to ``top_k`` nearest records honouring ``metadata_filter``."""
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k must be a positive int, got {top_k!r}")
        client = await self._get_client()
        hits = await client.search_points(
            list(vector), top_k=top_k, metadata_filter=metadata_filter
        )
        return [
            VectorMatch(
                id=hit["id"],
                score=float(hit["score"]),
                metadata=dict(hit.get("metadata", {})),
                document=hit.get("document"),
            )
            for hit in hits
        ]

    async def get(self, key: str) -> VectorRecord | None:
        """Return the record stored under ``key``, or ``None``."""
        client = await self._get_client()
        point = await client.get_point(key)
        if point is None:
            return None
        return VectorRecord.create(
            id=point["id"],
            vector=point["vector"],
            metadata=dict(point.get("metadata", {})),
            document=point.get("document"),
        )

    async def delete(self, ids: Sequence[str]) -> None:
        """Remove every record whose id is in ``ids``."""
        if not ids:
            return
        client = await self._get_client()
        await client.delete_points(list(ids))

    async def close(self) -> None:
        """Close the backend client and scrub credentials."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._clear_credentials()

    def _clear_credentials(self) -> None:
        """Drop the credential so the secret becomes GC-able."""
        self._credential = None
