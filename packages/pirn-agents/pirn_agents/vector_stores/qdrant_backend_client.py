"""``QdrantBackendClient`` — the real Qdrant wrapper behind the neutral client.

Implements :class:`~pirn_agents.vector_stores.vector_backend_client.VectorBackendClient`
by lazily importing ``qdrant_client`` (the ``[qdrant]`` extra) and translating the
neutral point/hit mappings and metadata filters into Qdrant's native models.
Importing this module pulls in no backend — the SDK is imported only when a
method actually runs, which happens under the ``needs_qdrant`` conformance run.

Qdrant point ids must be ints/UUIDs, so the neutral string id is preserved in
the payload and a deterministic UUID5 is used as the physical id.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.vector_stores.vector_backend_client import VectorBackendClient


class QdrantBackendClient(VectorBackendClient):
    """Neutral-client wrapper over an ``AsyncQdrantClient``."""

    def __init__(
        self,
        *,
        collection: str,
        dimension: int,
        url: str | None = None,
        credential: CredentialRef | None = None,
    ) -> None:
        """Initialise the wrapper without importing the backend.

        Args:
            collection: Target collection name.
            dimension: Vector dimension for the collection.
            url: Optional service URL; an in-memory client is used when absent.
            credential: Optional API-key credential.
        """
        self._collection: str = collection
        self._dimension: int = dimension
        self._url: str | None = url
        self._credential: CredentialRef | None = credential
        self._client: Any | None = None

    def _models(self) -> Any:
        """Return the lazily-imported ``qdrant_client.models`` module."""
        return _require("qdrant", "qdrant_client.models")

    async def _get_client(self) -> Any:
        """Build the async client and ensure the collection exists, once."""
        if self._client is None:
            qdrant_client = _require("qdrant", "qdrant_client")
            models = self._models()
            api_key = self._credential.reveal() if self._credential is not None else None
            client = qdrant_client.AsyncQdrantClient(location=self._url, api_key=api_key)
            if not await client.collection_exists(self._collection):
                await client.create_collection(
                    collection_name=self._collection,
                    vectors_config=models.VectorParams(
                        size=self._dimension, distance=models.Distance.COSINE
                    ),
                )
            self._client = client
        return self._client

    @staticmethod
    def _point_id(key: str) -> str:
        """Return a deterministic UUID5 physical id for a neutral string ``key``."""
        return str(uuid.uuid5(uuid.NAMESPACE_OID, key))

    def _to_filter(self, metadata_filter: Mapping[str, Any] | None) -> Any:
        """Translate a neutral metadata filter into a Qdrant ``Filter``."""
        if not metadata_filter:
            return None
        models = self._models()
        conditions: list[Any] = []
        for key, expected in metadata_filter.items():
            field = f"metadata.{key}"
            if isinstance(expected, list | tuple | set):
                match = models.MatchAny(any=list(expected))
            else:
                match = models.MatchValue(value=expected)
            conditions.append(models.FieldCondition(key=field, match=match))
        return models.Filter(must=conditions)

    async def upsert_points(self, points: Sequence[Mapping[str, Any]]) -> None:
        """Upsert neutral points as Qdrant ``PointStruct`` records."""
        client = await self._get_client()
        models = self._models()
        structs = [
            models.PointStruct(
                id=self._point_id(point["id"]),
                vector=list(point["vector"]),
                payload={
                    "_id": point["id"],
                    "metadata": dict(point.get("metadata", {})),
                    "document": point.get("document"),
                },
            )
            for point in points
        ]
        await client.upsert(collection_name=self._collection, points=structs)

    async def search_points(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        metadata_filter: Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]]:
        """Search Qdrant and return neutral hit mappings (cosine similarity score)."""
        client = await self._get_client()
        response = await client.query_points(
            collection_name=self._collection,
            query=list(vector),
            limit=top_k,
            query_filter=self._to_filter(metadata_filter),
            with_payload=True,
        )
        hits: list[Mapping[str, Any]] = []
        for scored in response.points:
            payload = scored.payload or {}
            hits.append(
                {
                    "id": payload.get("_id"),
                    "score": float(scored.score),
                    "metadata": dict(payload.get("metadata", {})),
                    "document": payload.get("document"),
                }
            )
        return hits

    async def get_point(self, key: str) -> Mapping[str, Any] | None:
        """Retrieve one point by neutral id, including its vector."""
        client = await self._get_client()
        records = await client.retrieve(
            collection_name=self._collection,
            ids=[self._point_id(key)],
            with_vectors=True,
            with_payload=True,
        )
        if not records:
            return None
        record = records[0]
        payload = record.payload or {}
        return {
            "id": payload.get("_id", key),
            "vector": list(record.vector or []),
            "metadata": dict(payload.get("metadata", {})),
            "document": payload.get("document"),
        }

    async def delete_points(self, ids: Sequence[str]) -> None:
        """Delete points by neutral id."""
        client = await self._get_client()
        models = self._models()
        await client.delete(
            collection_name=self._collection,
            points_selector=models.PointIdsList(points=[self._point_id(key) for key in ids]),
        )

    async def close(self) -> None:
        """Close the async client if one was built."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._credential = None
