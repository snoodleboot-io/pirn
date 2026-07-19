"""``PromptCache`` — exact + semantic LLM prompt cache with TTL and invalidation.

Two hit paths over one store:

* **Exact** — the prompt and its call parameters are content-addressed (reusing
  the DAG's :func:`~pirn_agents.caching.content_address.content_address`), so an
  identical ``prompt + params`` call short-circuits the model entirely.
* **Semantic** — when a caller-injected embedding function is supplied, a near
  duplicate prompt whose cosine similarity clears ``threshold`` also hits, so
  paraphrases reuse a prior answer.

Every entry carries an optional expiry stamped from an injectable ``clock`` (so
TTL behaviour is deterministic under test); expired entries are skipped on read
and can be swept with :meth:`purge_expired`. Entries are also explicitly
droppable with :meth:`invalidate`. No vendor SDK is imported — the embedding
function is the only backend seam — so the cache stays provider-neutral and
``import pirn_agents`` stays backend-free.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.content_address import content_address
from pirn_agents.evaluation.cosine_similarity import CosineSimilarity


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
            max_entries: Optional FIFO bound on stored entries.
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
        self._max_entries = max_entries
        self._clock = clock
        self._cosine = CosineSimilarity()
        self._entries: dict[str, CacheEntry] = {}
        self.hits = 0
        self.semantic_hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def key_for(prompt: str, params: Mapping[str, Any] | None = None) -> str:
        """Return the content-address key for a ``prompt`` and its ``params``."""
        return content_address({"prompt": prompt, "params": dict(params) if params else {}})

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
        exact = self._entries.get(key)
        if exact is not None and not self._is_expired(exact, now):
            self.hits += 1
            return exact.value
        if exact is not None:
            del self._entries[key]

        if self._embed is not None:
            query = tuple(float(x) for x in await self._embed(prompt))
            match = self._best_semantic(query, now)
            if match is not None:
                self.semantic_hits += 1
                return match.value
        else:
            query = None

        self.misses += 1
        value = await compute()
        self._store(CacheEntry(key=key, value=value, embedding=query, expires_at=self._expiry(now)))
        return value

    def invalidate(self, prompt: str, *, params: Mapping[str, Any] | None = None) -> None:
        """Explicitly drop the exact entry for ``prompt``/``params`` (a no-op if absent)."""
        self._entries.pop(self.key_for(prompt, params), None)

    def purge_expired(self) -> int:
        """Evict every expired entry, returning the number removed."""
        now = self._clock()
        stale = [key for key, entry in self._entries.items() if self._is_expired(entry, now)]
        for key in stale:
            del self._entries[key]
        return len(stale)

    def _best_semantic(self, query: tuple[float, ...], now: float) -> CacheEntry | None:
        """Return the best non-expired entry whose similarity clears ``threshold``."""
        best: CacheEntry | None = None
        best_similarity = self._threshold
        for entry in self._entries.values():
            if entry.embedding is None or self._is_expired(entry, now):
                continue
            similarity = (
                0.0
                if len(query) != len(entry.embedding)
                else self._cosine.compute(query, entry.embedding)
            )
            if similarity >= best_similarity:
                best = entry
                best_similarity = similarity
        return best

    def _store(self, entry: CacheEntry) -> None:
        """Insert ``entry`` with optional FIFO eviction of the oldest item."""
        if (
            self._max_entries is not None
            and entry.key not in self._entries
            and len(self._entries) >= self._max_entries
        ):
            del self._entries[next(iter(self._entries))]
        self._entries[entry.key] = entry

    def _expiry(self, now: float) -> float | None:
        """Return the absolute expiry stamp for an entry created at ``now``."""
        return None if self._ttl_seconds is None else now + self._ttl_seconds

    @staticmethod
    def _is_expired(entry: CacheEntry, now: float) -> bool:
        """Return whether ``entry`` has passed its expiry stamp at ``now``."""
        return entry.expires_at is not None and now >= entry.expires_at
