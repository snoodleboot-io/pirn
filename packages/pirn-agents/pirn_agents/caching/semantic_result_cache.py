"""``SemanticResultCache`` — a :class:`ResultCache` that matches by embedding similarity.

ADR agents-speaks-core WS2 part 2: "index = resource, values = DataStore".
:meth:`get_or_compute_semantic` needs a nearest-match scan over embeddings,
which needs enumeration —
:class:`pirn.backends.base.data_store.DataStore` deliberately exposes none
(``put``/``get``/``has``/``scrub`` only, keyed lookups by design). The
embeddings therefore live in a vended
:class:`~pirn_agents.caching.similarity_index.SimilarityIndex` resource
(exactly like a vector-store backend), keyed by the same ``content_hash``
string the matched entry is stored under; the entries themselves — the
actual cached *values* — live in an
:class:`~pirn.backends.in_memory.in_memory_data_store.InMemoryDataStore`,
the same store :class:`~pirn_agents.caching.in_memory_result_cache.InMemoryResultCache`
uses. Exact-key ``get``/``put``/``has``/``invalidate`` therefore delegate to
that store, keeping the index in sync alongside it, rather than overriding
every storage method with a private dict as before this pass.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.core.hashing import content_hash
from pirn.exceptions.value_evicted_error import ValueEvictedError

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.result_cache import ResultCache
from pirn_agents.caching.similarity_index import SimilarityIndex


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
            max_entries: Optional bound on stored entries (evicts the
                least-recently-*read* entry once reached, per
                :class:`InMemoryDataStore`).

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
        super().__init__(store=InMemoryDataStore(max_values=max_entries))
        self._embed = embed
        self._threshold = threshold
        self._index = SimilarityIndex()
        self.hits = 0
        self.misses = 0
        # Mirrors InMemoryResultCache's own bookkeeping: DataStore has no
        # count/enumeration, so __len__ tracks the key set it was given,
        # not the store's internal state.
        self._keys: set[str] = set()

    def __len__(self) -> int:
        return len(self._keys)

    async def get(self, key: str) -> CacheEntry | None:
        """Exact-key lookup (bumps hit/miss counters)."""
        try:
            entry = await self._store.get(key)
        except (KeyError, ValueEvictedError):
            entry = None
        if entry is None:
            self.misses += 1
            self._keys.discard(key)
            self._index.discard(key)
            return None
        self.hits += 1
        return entry

    async def put(self, entry: CacheEntry) -> None:
        """Store ``entry``, indexing its embedding (if any) for the semantic scan."""
        await self._store.put(entry.key, entry)
        self._keys.add(entry.key)
        if entry.embedding is not None:
            self._index.put(entry.key, entry.embedding)

    async def has(self, key: str) -> bool:
        """Return whether an entry is stored under the exact ``key``."""
        return await self._store.has(key)

    async def invalidate(self, key: str) -> None:
        """Drop the entry under ``key`` if present, from both the store and the index."""
        await self._store.scrub(key)
        self._keys.discard(key)
        self._index.discard(key)

    async def get_or_compute_semantic(
        self, text: str, compute: Callable[[], Awaitable[Any]]
    ) -> Any:
        """Return a semantically-matching cached value or compute and store one.

        Embeds ``text``, scans the similarity index for the best cosine match
        at or above ``threshold``, and returns its value on a hit. On a miss
        it computes the value, stores it keyed by the content hash of
        ``text`` (with its embedding indexed for future matches), and
        returns it.
        """
        query = tuple(float(x) for x in await self._embed(text))
        best_key = self._index.best_match(query, self._threshold)
        if best_key is not None:
            try:
                entry = await self._store.get(best_key)
            except (KeyError, ValueEvictedError):
                entry = None
                self._keys.discard(best_key)
                self._index.discard(best_key)
            if entry is not None:
                self.hits += 1
                return entry.value
        self.misses += 1
        value = await compute()
        await self.put(
            CacheEntry(key=content_hash(text, strict=True), value=value, embedding=query)
        )
        return value
