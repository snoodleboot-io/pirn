"""``VectorMemoryStore`` — a :class:`MemoryStore` over a vector upsert/query core.

Every concrete vector store (in-memory, pgvector, Qdrant, Chroma) shares one
vector-native contract expressed by four abstract coroutines:

* :meth:`upsert` — write :class:`VectorRecord` batches;
* :meth:`query` — nearest-neighbour search returning :class:`VectorMatch` hits,
  honouring an optional metadata filter;
* :meth:`get` — fetch a single record by id;
* :meth:`delete` — remove records by id.

On top of that core this base implements the keyed
:class:`pirn_agents.memory_store.MemoryStore` surface (``store``/``retrieve``/
``search``/``forget``) so a vector store drops into the existing memory + RAG
pipelines unchanged. ``search`` takes a text query, so the store optionally
holds an :class:`EmbeddingProvider` to turn that text into a query vector.

A single shared conformance suite exercises exactly these methods, which is why
all four adapters can be validated identically.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.vector_stores.vector_match import VectorMatch
from pirn_agents.vector_stores.vector_record import VectorRecord


class VectorMemoryStore(MemoryStore):
    """Abstract vector store exposing both vector-native and keyed surfaces."""

    def __init__(self, *, embedder: EmbeddingProvider | None = None) -> None:
        """Initialise the base store.

        Args:
            embedder: Optional embedding provider used by :meth:`search` to turn
                a text query into a query vector. Vector-native methods never
                need it.

        Raises:
            TypeError: If ``embedder`` is neither an ``EmbeddingProvider`` nor
                ``None``.
        """
        if embedder is not None and not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"embedder must be an EmbeddingProvider or None, got {type(embedder).__name__}"
            )
        self._embedder: EmbeddingProvider | None = embedder

    # --- vector-native core (abstract) ------------------------------------
    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert or overwrite each record by id."""
        raise NotImplementedError(f"{type(self).__name__} must implement upsert()")

    async def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Return up to ``top_k`` nearest records to ``vector`` matching the filter."""
        raise NotImplementedError(f"{type(self).__name__} must implement query()")

    async def get(self, key: str) -> VectorRecord | None:
        """Return the record stored under ``key``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    async def delete(self, ids: Sequence[str]) -> None:
        """Remove every record whose id is in ``ids`` (missing ids are ignored)."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete()")

    # --- keyed MemoryStore surface (concrete, built on the core) ----------
    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        """Upsert one record from a ``{"vector", "metadata"?, "document"?}`` mapping.

        Args:
            key: The record id.
            value: A mapping carrying a ``"vector"`` sequence and optional
                ``"metadata"`` mapping and ``"document"`` string.

        Raises:
            KeyError: If ``value`` has no ``"vector"`` entry.
        """
        vector = value["vector"]
        metadata = value.get("metadata", {})
        document = value.get("document")
        record = VectorRecord.create(id=key, vector=vector, metadata=metadata, document=document)
        await self.upsert([record])

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        """Return the record under ``key`` as a plain mapping, or ``None``."""
        record = await self.get(key)
        if record is None:
            return None
        return self._record_to_mapping(record)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Embed ``query`` and yield up to ``top_k`` nearest records as mappings.

        Args:
            query: The text query; embedded via the configured provider.
            top_k: Maximum number of hits to yield.

        Returns:
            An async iterator of hit mappings, each with ``id``, ``score``,
            ``metadata``, and ``document`` keys.

        Raises:
            RuntimeError: If no embedding provider was supplied at construction.
        """
        if self._embedder is None:
            raise RuntimeError(
                f"{type(self).__name__}.search() needs an embedder; construct the "
                "store with embedder=... or call query() with a vector directly"
            )
        vectors = await self._embedder.embed([query])
        matches = await self.query(vectors[0], top_k=top_k)

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for match in matches:
                yield {
                    "id": match.id,
                    "score": match.score,
                    "metadata": dict(match.metadata),
                    "document": match.document,
                }

        return _aiter()

    async def forget(self, key: str) -> None:
        """Remove the record stored under ``key`` if present."""
        await self.delete([key])

    @staticmethod
    def _record_to_mapping(record: VectorRecord) -> dict[str, Any]:
        """Return a plain-dict view of ``record`` for the keyed surface."""
        return {
            "id": record.id,
            "vector": list(record.vector),
            "metadata": dict(record.metadata),
            "document": record.document,
        }
