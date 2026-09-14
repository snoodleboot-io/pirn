"""``VectorMemoIndex`` — vended resource for exact-key vector memoisation.

ADR agents-speaks-core WS2 part 2: :class:`~pirn_agents.caching.embedding_cache.EmbeddingCache`
does no similarity scanning — it is pure exact-key memoisation, so unlike
:class:`~pirn_agents.caching.similarity_index.SimilarityIndex` there is
nothing to separate into "index" and "value": the vector *is* the value. It
is still framed as a vended :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`
resource, consistent with how the other embedding-indexed caches in this
package hold their in-process state, rather than a bare private dict.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class VectorMemoIndex(PirnOpaqueValue):
    """An in-process ``ContentHasher.hash`` key -> vector memoisation table."""

    def __init__(self, *, max_entries: int | None = None) -> None:
        """Create an empty, optionally FIFO-bounded index.

        Args:
            max_entries: Maximum distinct vectors retained; the oldest
                inserted key is evicted once the bound is reached. ``None``
                is unbounded.
        """
        self._max_entries = max_entries
        self._vectors: dict[str, tuple[float, ...]] = {}

    def __len__(self) -> int:
        return len(self._vectors)

    def __contains__(self, key: str) -> bool:
        return key in self._vectors

    def get(self, key: str) -> tuple[float, ...]:
        """Return the vector stored under ``key``.

        Raises:
            KeyError: If no vector is stored under ``key``.
        """
        return self._vectors[key]

    def put(self, key: str, vector: Sequence[float]) -> None:
        """Store ``vector`` under ``key``, evicting the oldest entry at the bound."""
        if (
            self._max_entries is not None
            and key not in self._vectors
            and len(self._vectors) >= self._max_entries
        ):
            del self._vectors[next(iter(self._vectors))]
        self._vectors[key] = tuple(float(x) for x in vector)

    def discard(self, key: str) -> None:
        """Remove ``key`` from the index, if present (a no-op otherwise)."""
        self._vectors.pop(key, None)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"size": len(self._vectors)}
