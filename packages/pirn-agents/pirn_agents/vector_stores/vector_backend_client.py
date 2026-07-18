"""``VectorBackendClient`` — the neutral async surface external stores talk to.

Qdrant and Chroma expose very different SDKs, so their
:class:`~pirn_agents.vector_stores.vector_memory_store.VectorMemoryStore`
adapters do not call those SDKs directly. Instead each adapter depends on this
provider-neutral base class and a thin backend wrapper implements it by lazily
importing and translating to the vendor SDK. That seam is what keeps the
adapters vendor-agnostic and lets mirrored tests inject an in-memory fake client
that runs the full conformance suite with no backend installed.

The base class raises :class:`NotImplementedError` for every method (the house
interface style — never :class:`typing.Protocol`) and is opaque
(:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`) because a concrete client
holds live vendor state (SDK client, credential): it drops into the pirn graph as
a config value by ``isinstance`` without descending into the content-addressed
hash. Model on the sibling :class:`~pirn_agents.graph_stores.graph_store.GraphStore`.

Points and hits are plain mappings:

* point — ``{"id", "vector", "metadata", "document"}``;
* hit  — ``{"id", "score", "metadata", "document"}`` (larger score = closer).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class VectorBackendClient(PirnOpaqueValue):
    """Abstract neutral async client every external vector backend is wrapped into."""

    async def upsert_points(self, points: Sequence[Mapping[str, Any]]) -> None:
        """Insert or overwrite each point mapping by its ``id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement upsert_points()")

    async def search_points(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        metadata_filter: Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``top_k`` hit mappings nearest to ``vector``."""
        raise NotImplementedError(f"{type(self).__name__} must implement search_points()")

    async def get_point(self, key: str) -> Mapping[str, Any] | None:
        """Return the point mapping stored under ``key``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement get_point()")

    async def delete_points(self, ids: Sequence[str]) -> None:
        """Remove every point whose id is in ``ids``."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete_points()")

    async def close(self) -> None:
        """Release the underlying backend client."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")
