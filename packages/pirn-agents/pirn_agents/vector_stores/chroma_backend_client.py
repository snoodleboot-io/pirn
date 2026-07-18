"""``ChromaBackendClient`` — the real Chroma wrapper behind the neutral client.

Implements :class:`~pirn_agents.vector_stores.vector_backend_client.VectorBackendClient`
by lazily importing ``chromadb`` (the ``[chroma]`` extra) and translating the
neutral point/hit mappings and metadata filters into Chroma's collection API.
Chroma's client is synchronous, so every call is offloaded to a worker thread
via :func:`asyncio.to_thread` to keep the event loop free. Importing this module
pulls in no backend — the SDK is imported only when a method runs, under the
``needs_chroma`` conformance run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.vector_stores.vector_backend_client import VectorBackendClient


class ChromaBackendClient(VectorBackendClient):
    """Neutral-client wrapper over a Chroma collection (cosine space)."""

    def __init__(self, *, collection: str, persist_path: str | None = None) -> None:
        """Initialise the wrapper without importing the backend.

        Args:
            collection: Target collection name.
            persist_path: Optional on-disk path; an ephemeral client is used
                when absent.
        """
        self._collection_name: str = collection
        self._persist_path: str | None = persist_path
        self._collection: Any | None = None

    def _get_collection(self) -> Any:
        """Build the client and get-or-create the cosine collection, once."""
        if self._collection is None:
            chromadb = _require("chroma", "chromadb")
            if self._persist_path is not None:
                client = chromadb.PersistentClient(path=self._persist_path)
            else:
                client = chromadb.EphemeralClient()
            self._collection = client.get_or_create_collection(
                name=self._collection_name, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    @staticmethod
    def _to_where(metadata_filter: Mapping[str, Any] | None) -> Any:
        """Translate a neutral metadata filter into a Chroma ``where`` clause."""
        if not metadata_filter:
            return None
        clauses: list[dict[str, Any]] = []
        for key, expected in metadata_filter.items():
            if isinstance(expected, list | tuple | set):
                clauses.append({key: {"$in": list(expected)}})
            else:
                clauses.append({key: expected})
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    async def upsert_points(self, points: Sequence[Mapping[str, Any]]) -> None:
        """Upsert neutral points into the collection (thread-offloaded)."""
        collection = self._get_collection()
        ids = [point["id"] for point in points]
        embeddings = [list(point["vector"]) for point in points]
        metadatas = [dict(point.get("metadata", {})) or None for point in points]
        documents = [point.get("document") for point in points]

        def _run() -> None:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )

        await asyncio.to_thread(_run)

    async def search_points(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        metadata_filter: Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]]:
        """Query the collection and return neutral hits (cosine similarity score)."""
        collection = self._get_collection()
        where = self._to_where(metadata_filter)

        def _run() -> Any:
            return collection.query(
                query_embeddings=[list(vector)],
                n_results=top_k,
                where=where,
                include=["metadatas", "documents", "distances"],
            )

        result = await asyncio.to_thread(_run)
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        hits: list[Mapping[str, Any]] = []
        for index, identifier in enumerate(ids):
            hits.append(
                {
                    "id": identifier,
                    "score": 1.0 - float(distances[index]),
                    "metadata": dict(metadatas[index] or {}),
                    "document": documents[index],
                }
            )
        return hits

    async def get_point(self, key: str) -> Mapping[str, Any] | None:
        """Fetch one point (with its vector) by id, thread-offloaded."""
        collection = self._get_collection()

        def _run() -> Any:
            return collection.get(ids=[key], include=["embeddings", "metadatas", "documents"])

        result = await asyncio.to_thread(_run)
        ids = result.get("ids") or []
        if not ids:
            return None
        embeddings = result.get("embeddings") or [[]]
        metadatas = result.get("metadatas") or [{}]
        documents = result.get("documents") or [None]
        return {
            "id": ids[0],
            "vector": list(embeddings[0]),
            "metadata": dict(metadatas[0] or {}),
            "document": documents[0],
        }

    async def delete_points(self, ids: Sequence[str]) -> None:
        """Delete points by id, thread-offloaded."""
        collection = self._get_collection()
        id_list = list(ids)

        def _run() -> None:
            collection.delete(ids=id_list)

        await asyncio.to_thread(_run)

    async def close(self) -> None:
        """Drop the collection handle (Chroma clients need no explicit close)."""
        self._collection = None
