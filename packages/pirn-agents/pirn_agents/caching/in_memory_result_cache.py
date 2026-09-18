"""``InMemoryResultCache`` — pure-python default :class:`ResultCache` (ADR agents-speaks-core WS2).

Backed by :class:`pirn.backends.in_memory.in_memory_data_store.InMemoryDataStore`
rather than a private dict, so the bounding, eviction, and content-addressing
this class used to hand-roll are core's — this is the same store the engine
uses for knot outputs, with hit/miss counters on top.
"""

from __future__ import annotations

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.result_cache import ResultCache
from pirn_agents.caching.tracked_store_keys import TrackedStoreKeys


class InMemoryResultCache(ResultCache):
    """A store-backed cache with optional bounding and hit/miss counters.

    The zero-dependency default: no external backend, deterministic, and fast
    enough for within-run memoisation of idempotent calls. When ``max_entries``
    is set the least-recently-*read* entry is evicted once the bound is
    reached — :class:`InMemoryDataStore`'s eviction order — so neither the cache
    nor the key set mirroring it grows without limit.
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
        super().__init__(store=InMemoryDataStore(max_values=max_entries))
        self.hits = 0
        self.misses = 0
        # DataStore exposes no count/enumeration (put/get/has/scrub only), so
        # the key set is mirrored here to answer __len__ without reaching into
        # the store's private state. It is pruned against the store after every
        # write, so a bounded cache's key set cannot outgrow what the store
        # actually holds (PIR-873).
        self._tracked = TrackedStoreKeys(self.store, bounded=max_entries is not None)

    def __len__(self) -> int:
        return len(self._tracked)

    async def invalidate(self, key: str) -> None:
        """Drop the entry under ``key`` if present."""
        await super().invalidate(key)
        self._tracked.discard(key)

    async def _lookup(self, key: str) -> CacheEntry | None:
        """Look ``key`` up and bump the hit/miss counters."""
        entry = await super()._lookup(key)
        if entry is None:
            self.misses += 1
            # A tracked key with no entry was evicted by the store's own
            # bound; stop counting it so __len__ reflects what is retrievable.
            self._tracked.discard(key)
            return None
        self.hits += 1
        return entry

    async def _record(self, entry: CacheEntry) -> None:
        """Store ``entry``, evicting per :class:`InMemoryDataStore`'s bound."""
        await super()._record(entry)
        self._tracked.add(entry.key)
        await self._tracked.prune()
