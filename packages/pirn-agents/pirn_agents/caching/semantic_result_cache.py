"""``SemanticResultCache`` — a :class:`ResultCache` that matches by embedding similarity."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.content_address import content_address
from pirn_agents.caching.result_cache import ResultCache


class SemanticResultCache(ResultCache):
    """Cache that treats *near-identical* queries as hits, not just exact ones.

    Exact-key ``get``/``put``/``invalidate`` behave like the in-memory cache, so
    it is a drop-in :class:`ResultCache`. The extra
    :meth:`get_or_compute_semantic` path embeds the query text with a
    caller-injected embedding function and returns a stored value whose cosine
    similarity clears ``threshold`` — so paraphrased or reordered inputs still
    hit. The embedding function is injected (no vendor SDK is imported here),
    keeping the cache provider-neutral and backend-free.
    """

    def __init__(
        self,
        *,
        embed: Callable[[str], Awaitable[Sequence[float]]],
        threshold: float = 0.95,
        max_entries: int | None = None,
    ) -> None:
        """Create a semantic cache.

        Args:
            embed: Async function mapping text to a vector; the only backend
                seam, supplied by the caller.
            threshold: Minimum cosine similarity (0..1) for a semantic hit.
            max_entries: Optional FIFO bound on stored entries.

        Raises:
            ValueError: If ``threshold`` is outside ``[0, 1]`` or ``max_entries``
                is set and less than 1.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"SemanticResultCache: threshold must be in [0, 1], got {threshold!r}")
        if max_entries is not None and max_entries < 1:
            raise ValueError(
                f"SemanticResultCache: max_entries must be >= 1 or None, got {max_entries!r}"
            )
        self._embed = embed
        self._threshold = threshold
        self._max_entries = max_entries
        self._entries: dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    async def get(self, key: str) -> CacheEntry | None:
        """Exact-key lookup (bumps hit/miss counters)."""
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return entry

    async def put(self, entry: CacheEntry) -> None:
        """Store ``entry`` with optional FIFO eviction."""
        if (
            self._max_entries is not None
            and entry.key not in self._entries
            and len(self._entries) >= self._max_entries
        ):
            del self._entries[next(iter(self._entries))]
        self._entries[entry.key] = entry

    async def invalidate(self, key: str) -> None:
        """Drop the entry under ``key`` if present."""
        self._entries.pop(key, None)

    async def get_or_compute_semantic(
        self, text: str, compute: Callable[[], Awaitable[Any]]
    ) -> Any:
        """Return a semantically-matching cached value or compute and store one.

        Embeds ``text``, scans stored entries for the best cosine match at or
        above ``threshold``, and returns its value on a hit. On a miss it
        computes the value, stores it keyed by the content address of ``text``
        (with its embedding attached for future matches), and returns it.
        """
        query = tuple(float(x) for x in await self._embed(text))
        best: CacheEntry | None = None
        best_similarity = self._threshold
        for entry in self._entries.values():
            if entry.embedding is None:
                continue
            similarity = self._cosine(query, entry.embedding)
            if similarity >= best_similarity:
                best = entry
                best_similarity = similarity
        if best is not None:
            self.hits += 1
            return best.value
        self.misses += 1
        value = await compute()
        await self.put(CacheEntry(key=content_address(text), value=value, embedding=query))
        return value

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        """Cosine similarity of two equal-length vectors; 0.0 on degenerate input."""
        if len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        norm_left = math.sqrt(sum(a * a for a in left))
        norm_right = math.sqrt(sum(b * b for b in right))
        if norm_left == 0.0 or norm_right == 0.0:
            return 0.0
        return dot / (norm_left * norm_right)
