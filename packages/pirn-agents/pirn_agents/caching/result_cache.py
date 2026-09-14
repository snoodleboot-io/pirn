"""``ResultCache`` — compute-on-miss memoisation whose values live in a core ``DataStore``.

ADR agents-speaks-core WS2, collapsed further by PIR-872: ``DataStore`` is
already "where intermediate values live, keyed by content hash", so a cache
that re-exposed ``get``/``put``/``has`` over one was a second keyed-store
surface shadowing the core seam. ``ResultCache`` now adds only what a store
lacks — deriving a content-address key from an operation's *inputs* and
computing on a miss (:meth:`get_or_compute`), plus dropping a key
(:meth:`invalidate`). Raw keyed access is the store itself (:attr:`store`).
Swapping the store — in-memory today, a durable backend later — needs no
change here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.core.hashing import content_hash
from pirn.exceptions.value_evicted_error import ValueEvictedError

from pirn_agents.caching.cache_entry import CacheEntry


class ResultCache:
    """Content-addressed compute-on-miss memoisation over a core :class:`DataStore`.

    :meth:`get_or_compute` is the entry point: it derives a content-address
    key from the *inputs*, returns a hit when present, and otherwise computes,
    stores, and returns — the opt-in caching of an idempotent tool call or
    embedding lookup in one call.

    It stays a *plain* class (no :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`)
    because no knot holds a cache as a config value.
    """

    def __init__(self, *, store: DataStore) -> None:
        """Wrap ``store`` as a result cache.

        Args:
            store: The core ``DataStore`` values are read from and written to,
                keyed by content-address string. Its :attr:`DataStore.retention`
                governs how many results this cache holds — see
                :class:`InMemoryResultCache` for the bounded default.
        """
        self._store = store

    @property
    def store(self) -> DataStore:
        """The core ``DataStore`` holding this cache's entries — its keyed access."""
        return self._store

    async def get_or_compute(
        self,
        payload: Any,
        compute: Callable[[], Awaitable[Any]],
        *,
        embedding: tuple[float, ...] | None = None,
    ) -> Any:
        """Return a cached value for ``payload`` or compute, store, and return it.

        Args:
            payload: The operation inputs; content-addressed into the cache key,
                so identical inputs hit the same entry.
            compute: Async factory invoked only on a miss to produce the value.
            embedding: Optional vector stored with the entry for later semantic
                matching.

        Returns:
            The cached (on hit) or freshly computed (on miss) value.
        """
        key = content_hash(payload, strict=True)
        hit = await self._lookup(key)
        if hit is not None:
            return hit.value
        value = await compute()
        await self._record(CacheEntry(key=key, value=value, embedding=embedding))
        return value

    async def invalidate(self, key: str) -> None:
        """Drop any entry stored under ``key`` (a no-op if absent)."""
        await self._store.scrub(key)

    async def _lookup(self, key: str) -> CacheEntry | None:
        """Return the entry under ``key``, or ``None`` on a miss.

        A value the store evicted to stay within its
        :attr:`~pirn.backends.base.data_store.DataStore.retention` ceiling is
        reported the same way as one never stored — a miss, never a raised
        error — because a cache is optional by construction: an evicted result
        is simply recomputed.
        """
        try:
            return await self._store.get(key)
        except (KeyError, ValueEvictedError):
            return None

    async def _record(self, entry: CacheEntry) -> None:
        """Store ``entry`` under its :attr:`CacheEntry.key`."""
        await self._store.put(entry.key, entry)
