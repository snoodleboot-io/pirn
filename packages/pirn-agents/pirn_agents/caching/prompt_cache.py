"""``PromptCache`` — exact + semantic LLM prompt cache with TTL and invalidation.

Two hit paths over one store:

* **Exact** — the prompt and its call parameters are content-addressed via
  :meth:`pirn.core.content_hasher.ContentHasher.hash`, so an identical ``prompt + params``
  call short-circuits the model entirely.
* **Semantic** — when a caller-injected embedding function is supplied, a near
  duplicate prompt whose cosine similarity clears ``threshold`` also hits, so
  paraphrases reuse a prior answer.

Every entry carries an optional expiry stamped from an injectable ``clock`` (so
TTL behaviour is deterministic under test); expired entries are skipped on read
and can be swept with :meth:`apurge_expired`. Entries are also explicitly
droppable with :meth:`ainvalidate`. No vendor SDK is imported — the embedding
function is the only backend seam — so the cache stays provider-neutral and
``import pirn_agents`` stays backend-free.

ADR agents-speaks-core WS2 part 2 (PIR-868): "index = resource, values =
DataStore" is now fully applied here, exactly like
:class:`~pirn_agents.caching.semantic_result_cache.SemanticResultCache`.
Entries live in a core
:class:`~pirn.backends.in_memory.in_memory_data_store.InMemoryDataStore`,
keyed by the same content-hash string :meth:`key_for` has always produced;
the embeddings stay in the vended
:class:`~pirn_agents.caching.similarity_index.SimilarityIndex` resource.
``DataStore`` is async-only (``put``/``get``/``has``/``scrub``, and
deliberately exposes no enumeration), so the cache's management surface is
async too: :meth:`ainvalidate`, :meth:`apurge_expired`, and :meth:`asize`.
:meth:`apurge_expired` has no ``DataStore``-native "walk every entry"
primitive to call, so it mirrors :class:`SemanticResultCache`'s own
``_keys`` bookkeeping: a parallel ``set[str]`` of live keys, checked one at a
time against the store.

Eviction bound: delegated to ``InMemoryDataStore(max_values=max_entries)``,
which evicts the least-recently-*read* entry once full — a change from the
previous private dict's first-inserted-wins bound, but the same eviction
policy :class:`SemanticResultCache` already uses for the same reason (one
``DataStore`` implementation, one eviction policy).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.core.content_hasher import ContentHasher
from pirn.exceptions.value_evicted_error import ValueEvictedError

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.similarity_index import SimilarityIndex
from pirn_agents.caching.tracked_store_keys import TrackedStoreKeys


class PromptCache:
    """Content-addressed exact cache plus optional semantic near-duplicate cache."""

    def __init__(
        self,
        *,
        embed: Callable[[str], Awaitable[Sequence[float]]] | None = None,
        threshold: float = 0.95,
        ttl_seconds: float | None = None,
        max_entries: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a prompt cache.

        Args:
            embed: Async function mapping prompt text to a vector; the only
                backend seam. When ``None`` the cache is exact-only.
            threshold: Minimum cosine similarity (0..1) for a semantic hit.
            ttl_seconds: Entry lifetime in ``clock`` units; ``None`` never
                expires. Must be non-negative when set.
            max_entries: Optional bound on stored entries, enforced by the
                underlying :class:`InMemoryDataStore` (evicts the
                least-recently-read entry once full).
            clock: Monotonic clock source for TTL accounting, injectable so
                expiry is deterministic under test.

        Raises:
            ValueError: If ``threshold`` is outside ``[0, 1]``, ``ttl_seconds``
                is negative, or ``max_entries`` is set and less than 1.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"PromptCache: threshold must be in [0, 1], got {threshold!r}")
        if ttl_seconds is not None and ttl_seconds < 0:
            raise ValueError(f"PromptCache: ttl_seconds must be >= 0 or None, got {ttl_seconds!r}")
        if max_entries is not None and max_entries < 1:
            raise ValueError(f"PromptCache: max_entries must be >= 1 or None, got {max_entries!r}")
        self._embed = embed
        self._threshold = threshold
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._store = InMemoryDataStore(max_values=max_entries)
        self._index = SimilarityIndex()
        # DataStore exposes no count or enumeration; this mirrors
        # SemanticResultCache's own bookkeeping so `asize()` and
        # `apurge_expired()` don't need one either. Pruned against the store
        # after every write — and the similarity index with it — so a bounded
        # cache's key set and index cannot outgrow the store (PIR-873).
        self._tracked = TrackedStoreKeys(self._store, bounded=max_entries is not None)
        self.hits = 0
        self.semantic_hits = 0
        self.misses = 0

    async def asize(self) -> int:
        """Return the number of live (not yet evicted) entries."""
        await self._tracked.prune()
        return len(self._tracked)

    @staticmethod
    def key_for(prompt: str, params: Mapping[str, Any] | None = None) -> str:
        """Return the content-hash key for a ``prompt`` and its ``params``."""
        return ContentHasher.hash(
            {"prompt": prompt, "params": dict(params) if params else {}}, strict=True
        )

    async def get_or_compute(
        self,
        prompt: str,
        compute: Callable[[], Awaitable[Any]],
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Return a cached completion for ``prompt`` or compute, store, and return it.

        Tries the exact content-address first, then (when an embedder is
        configured) the best semantic match at or above ``threshold``. On a miss
        the value is computed, embedded if possible, stamped with the TTL, and
        stored.

        Args:
            prompt: The prompt text.
            compute: Async factory invoked only on a miss to produce the value.
            params: Call parameters (model, temperature, ...) folded into the
                exact key so differing params never collide.

        Returns:
            The cached (on hit) or freshly computed (on miss) value.
        """
        now = self._clock()
        key = self.key_for(prompt, params)
        exact = await self._get_entry(key)
        if exact is not None and not self._is_expired(exact, now):
            self.hits += 1
            return exact.value
        if exact is not None:
            await self._adiscard(key)

        if self._embed is not None:
            query = tuple(float(x) for x in await self._embed(prompt))
            match = await self._best_semantic(query, now)
            if match is not None:
                self.semantic_hits += 1
                return match.value
        else:
            query = None

        self.misses += 1
        value = await compute()
        await self._astore(
            CacheEntry(key=key, value=value, embedding=query, expires_at=self._expiry(now))
        )
        return value

    async def ainvalidate(self, prompt: str, *, params: Mapping[str, Any] | None = None) -> None:
        """Explicitly drop the exact entry for ``prompt``/``params`` (a no-op if absent)."""
        await self._adiscard(self.key_for(prompt, params))

    async def apurge_expired(self) -> int:
        """Evict every expired entry, returning the number removed."""
        now = self._clock()
        stale: list[str] = []
        for key in self._tracked.snapshot():
            entry = await self._get_entry(key)
            if entry is None or self._is_expired(entry, now):
                stale.append(key)
        for key in stale:
            await self._adiscard(key)
        return len(stale)

    async def _get_entry(self, key: str) -> CacheEntry | None:
        """Return the stored entry for ``key``, or ``None`` on a miss or eviction."""
        try:
            return await self._store.get(key)
        except (KeyError, ValueEvictedError):
            self._tracked.discard(key)
            self._index.discard(key)
            return None

    async def _best_semantic(self, query: tuple[float, ...], now: float) -> CacheEntry | None:
        """Return the best non-expired entry whose similarity clears ``threshold``.

        Walks the index's ranked candidates best-first rather than trusting
        the top-ranked one outright: the index knows nothing about expiry
        (that lives on the entry, in the ``DataStore``), so a stale top match
        is discarded and the next-best candidate is tried instead.
        """
        for key in self._index.ranked_matches(query, self._threshold):
            entry = await self._get_entry(key)
            if entry is None:
                continue
            if self._is_expired(entry, now):
                await self._adiscard(key)
                continue
            return entry
        return None

    async def _astore(self, entry: CacheEntry) -> None:
        """Insert ``entry`` (and index its embedding) into the store."""
        await self._store.put(entry.key, entry)
        self._tracked.add(entry.key)
        if entry.embedding is not None:
            self._index.put(entry.key, entry.embedding)
        for evicted in await self._tracked.prune():
            self._index.discard(evicted)

    async def _adiscard(self, key: str) -> None:
        """Remove ``key`` from the store, the key set, and the similarity index."""
        await self._store.scrub(key)
        self._tracked.discard(key)
        self._index.discard(key)

    def _expiry(self, now: float) -> float | None:
        """Return the absolute expiry stamp for an entry created at ``now``."""
        return None if self._ttl_seconds is None else now + self._ttl_seconds

    @staticmethod
    def _is_expired(entry: CacheEntry, now: float) -> bool:
        """Return whether ``entry`` has passed its expiry stamp at ``now``."""
        return entry.expires_at is not None and now >= entry.expires_at
