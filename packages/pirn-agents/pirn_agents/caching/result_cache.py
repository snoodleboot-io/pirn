"""``ResultCache`` — provider-neutral async cache interface for idempotent results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.content_address import content_address


class ResultCache(ABC):
    """The seam every cache backend implements: exact get/put/invalidate by key.

    The three abstract methods are the whole storage contract. The concrete
    :meth:`get_or_compute` layered on top is the ergonomic entry point callers
    actually use: it derives a content-address key from the *inputs*, returns a
    hit when present, and otherwise computes, stores, and returns — the opt-in
    caching of an idempotent tool call or embedding lookup in one call.
    """

    @abstractmethod
    async def get(self, key: str) -> CacheEntry | None:
        """Return the entry stored under ``key``, or ``None`` on a miss."""
        raise NotImplementedError

    @abstractmethod
    async def put(self, entry: CacheEntry) -> None:
        """Store ``entry`` under its :attr:`CacheEntry.key`."""
        raise NotImplementedError

    @abstractmethod
    async def invalidate(self, key: str) -> None:
        """Drop any entry stored under ``key`` (a no-op if absent)."""
        raise NotImplementedError

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
        key = content_address(payload)
        hit = await self.get(key)
        if hit is not None:
            return hit.value
        value = await compute()
        await self.put(CacheEntry(key=key, value=value, embedding=embedding))
        return value
