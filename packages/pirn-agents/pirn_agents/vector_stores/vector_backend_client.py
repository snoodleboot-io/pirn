"""``VectorBackendClient`` — the neutral async surface external stores talk to.

Qdrant and Chroma expose very different SDKs, so their
:class:`~pirn_agents.vector_stores.vector_memory_store.VectorMemoryStore`
adapters do not call those SDKs directly. Instead each adapter depends on this
provider-neutral protocol and a thin backend wrapper implements it by lazily
importing and translating to the vendor SDK. That seam is what keeps the
adapters vendor-agnostic and lets mirrored tests inject an in-memory fake client
that runs the full conformance suite with no backend installed.

Points and hits are plain mappings:

* point — ``{"id", "vector", "metadata", "document"}``;
* hit  — ``{"id", "score", "metadata", "document"}`` (larger score = closer).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorBackendClient(Protocol):
    """Neutral async client every external vector backend is wrapped into."""

    async def upsert_points(self, points: Sequence[Mapping[str, Any]]) -> None:
        """Insert or overwrite each point mapping by its ``id``."""
        ...

    async def search_points(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        metadata_filter: Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``top_k`` hit mappings nearest to ``vector``."""
        ...

    async def get_point(self, key: str) -> Mapping[str, Any] | None:
        """Return the point mapping stored under ``key``, or ``None``."""
        ...

    async def delete_points(self, ids: Sequence[str]) -> None:
        """Remove every point whose id is in ``ids``."""
        ...

    async def close(self) -> None:
        """Release the underlying backend client."""
        ...
