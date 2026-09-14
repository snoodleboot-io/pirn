"""``ResultCache`` — provider-neutral async cache, thin over a core ``DataStore``.

ADR agents-speaks-core WS2: this used to be a house-interface base class (three
``NotImplementedError`` storage methods) with :class:`InMemoryResultCache` as
its only real backend — a second, parallel key-value store next to
:class:`pirn.backends.base.data_store.DataStore`, which already exists for
exactly this job ("where intermediate values live, keyed by content hash").
``ResultCache`` now composes a ``DataStore`` and is concrete: :meth:`get`,
:meth:`put`, :meth:`has`, and :meth:`invalidate` all delegate to it, keyed by
the content-address string the caller (or :meth:`get_or_compute`) supplies.
Swapping the store — in-memory today, a durable backend later — needs no
change here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.core.content_hasher import ContentHasher
from pirn.exceptions.value_evicted_error import ValueEvictedError

from pirn_agents.caching.cache_entry import CacheEntry


class ResultCache:
    """Content-addressed result cache backed by a core :class:`DataStore`.

    The concrete :meth:`get_or_compute` layered on top is the ergonomic entry
    point callers actually use: it derives a content-address key from the
    *inputs*, returns a hit when present, and otherwise computes, stores, and
    returns — the opt-in caching of an idempotent tool call or embedding
    lookup in one call.

    It stays a *plain* class (no :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`)
    because no knot holds a cache as a config value; a future story that wires
    a cache into a ``KnotConfig`` would flip it to the opaque base.
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

    async def get(self, key: str) -> CacheEntry | None:
        """Return the entry stored under ``key``, or ``None`` on a miss.

        A value the store evicted to stay within its
        :attr:`~pirn.backends.base.data_store.DataStore.retention` ceiling is
        reported the same way as one that was never stored — a cache miss,
        never a raised error — because a cache is optional by construction:
        an evicted result is simply recomputed.
        """
        try:
            return await self._store.get(key)
        except ValueEvictedError:
            return None
        except KeyError:
            return None

    async def put(self, entry: CacheEntry) -> None:
        """Store ``entry`` under its :attr:`CacheEntry.key`."""
        await self._store.put(entry.key, entry)

    async def has(self, key: str) -> bool:
        """Return ``True`` if an entry is stored under ``key``."""
        return await self._store.has(key)

    async def invalidate(self, key: str) -> None:
        """Drop any entry stored under ``key`` (a no-op if absent)."""
        await self._store.scrub(key)

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
        key = ContentHasher.hash(payload, strict=True)
        hit = await self.get(key)
        if hit is not None:
            return hit.value
        value = await compute()
        await self.put(CacheEntry(key=key, value=value, embedding=embedding))
        return value
