"""``InMemoryResultCache`` — pure-python default :class:`ResultCache` with FIFO bounding."""

from __future__ import annotations

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.result_cache import ResultCache


class InMemoryResultCache(ResultCache):
    """A dict-backed cache with optional FIFO eviction and hit/miss counters.

    The zero-dependency default: no backend, deterministic, and fast enough for
    within-run memoisation of idempotent calls. When ``max_entries`` is set the
    oldest inserted entry is evicted once the bound is reached, so the cache
    never grows without limit.
    """

    def __init__(self, *, max_entries: int | None = None) -> None:
        """Create an empty cache, optionally bounded to ``max_entries`` items.

        Raises:
            ValueError: If ``max_entries`` is set and is less than 1.
        """
        if max_entries is not None and max_entries < 1:
            raise ValueError(
                f"InMemoryResultCache: max_entries must be >= 1 or None, got {max_entries!r}"
            )
        self._entries: dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    async def get(self, key: str) -> CacheEntry | None:
        """Return the entry for ``key`` and bump the hit/miss counters."""
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return entry

    async def put(self, entry: CacheEntry) -> None:
        """Store ``entry``, evicting the oldest item if the bound is reached."""
        if (
            self._max_entries is not None
            and entry.key not in self._entries
            and len(self._entries) >= self._max_entries
        ):
            oldest_key = next(iter(self._entries))
            del self._entries[oldest_key]
        self._entries[entry.key] = entry

    async def invalidate(self, key: str) -> None:
        """Drop the entry under ``key`` if present."""
        self._entries.pop(key, None)
