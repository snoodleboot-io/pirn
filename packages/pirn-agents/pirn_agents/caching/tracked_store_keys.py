"""``TrackedStoreKeys`` — the live key set mirroring a ``DataStore`` that cannot enumerate.

``DataStore`` is keyed lookup only — ``put``/``get``/``has``/``scrub``, no count
and no enumeration, deliberately — so a cache built on one keeps its own set of
the keys it has written in order to answer ``len()`` / ``asize()`` and to walk
its entries for expiry.

That set is the thing that leaks. A bounded store evicts *silently*: the value
is gone and nothing tells the cache which key went. Three caches
(``InMemoryResultCache``, ``SemanticResultCache``, ``PromptCache``) only dropped
a key when that same key was looked up and missed, so a long-lived bounded cache
grew its key set — and ``SemanticResultCache``/``PromptCache`` their similarity
index, which is scanned on every semantic lookup — for the whole life of the
process while the store held at most ``max_entries`` values. The reported size
was the number of keys ever written, not the number retrievable (PIR-873).

``EmbeddingCache`` had the right shape: prune the tracked keys against the store
after every write. This class is that shape, owned once, so all four caches
share it instead of keeping four copies of the bookkeeping.

Algorithm:
    1. ``add`` / ``discard`` maintain the set.
    2. ``prune`` — after a write into a *bounded* store — asks the store
       ``has(key)`` for each tracked key, drops the ones it no longer holds, and
       returns them, so a caller keeping a parallel structure (a similarity
       index) can drop the same keys. On an unbounded store nothing can be
       evicted, so it is a no-op and costs nothing.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from pirn.backends.base.data_store import DataStore


class TrackedStoreKeys:
    """The set of keys a cache has written into a ``DataStore``, kept honest."""

    def __init__(self, store: DataStore, *, bounded: bool) -> None:
        """Track the keys written into ``store``.

        Args:
            store: The store the keys were written to.
            bounded: Whether the store can evict — ``True`` when it was given a
                ``max_values`` ceiling. ``prune`` is a no-op when ``False``,
                because an unbounded store never drops a value.

        Raises:
            TypeError: If ``store`` is not a ``DataStore``.
        """
        if not isinstance(store, DataStore):
            raise TypeError(
                f"TrackedStoreKeys: store must be a DataStore, got {type(store).__name__}"
            )
        self._store = store
        self._bounded = bool(bounded)
        self._keys: set[str] = set()

    def __len__(self) -> int:
        """The number of keys currently believed to be retrievable."""
        return len(self._keys)

    def __contains__(self, key: object) -> bool:
        """Whether ``key`` is currently tracked."""
        return key in self._keys

    def snapshot(self) -> tuple[str, ...]:
        """The tracked keys, sorted, as a stable list safe to iterate while mutating."""
        return tuple(sorted(self._keys))

    def add(self, key: str) -> None:
        """Track ``key`` as written."""
        self._keys.add(key)

    def discard(self, key: str) -> None:
        """Stop tracking ``key``."""
        self._keys.discard(key)

    async def prune(self) -> tuple[str, ...]:
        """Drop every tracked key the store no longer holds; return those keys.

        Returns:
            The keys dropped, sorted — empty on an unbounded store, and empty
            when the store still holds everything tracked.
        """
        if not self._bounded:
            return ()
        evicted: list[str] = []
        for key in self.snapshot():
            if not await self._store.has(key):
                evicted.append(key)
        for key in evicted:
            self._keys.discard(key)
        return tuple(evicted)
