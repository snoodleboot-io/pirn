"""``EmbeddingCache`` — memoise embedding vectors by content hash across providers.

Embedding the same text twice is pure waste: the vector is a deterministic
function of ``(text, model)``. This cache keys each text by
:meth:`pirn.core.content_hasher.ContentHasher.hash` (folding in the model so different
models never collide) and only calls the wrapped embed function for texts it
has never seen. Re-indexing an overlapping corpus therefore collapses to
embedding just the *new* texts — the counters :attr:`provider_calls` and
:attr:`served_from_cache` make that saving measurable.

The wrapped embed function is the sole backend seam — any
:class:`pirn_agents.retrieval.embeddings.embedding_provider.EmbeddingProvider` ``embed`` (or a
plain async callable) fits — so the cache is provider-neutral and no vendor SDK
is imported here.

This is pure exact-key memoisation (no similarity scan anywhere), so the vector
*is* the value, and values live in a core
:class:`~pirn.backends.in_memory.in_memory_data_store.InMemoryDataStore` keyed
by the content hash — the same store :class:`PromptCache` and
:class:`SemanticResultCache` use (PIR-872 deleted the private ``VectorMemoIndex``
key-value table this used to keep beside it). ``DataStore`` is async-only, so
:meth:`invalidate` is a coroutine.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.core.content_hasher import ContentHasher
from pirn.exceptions.value_evicted_error import ValueEvictedError

from pirn_agents.caching.tracked_store_keys import TrackedStoreKeys


class EmbeddingCache:
    """Content-hash memoisation in front of a provider-neutral batch embed call."""

    def __init__(
        self,
        embed: Callable[[Sequence[str]], Awaitable[Sequence[Sequence[float]]]],
        *,
        max_entries: int | None = None,
    ) -> None:
        """Wrap a batch embed function with content-hash memoisation.

        Args:
            embed: Async function returning one vector per input text, in order —
                the only backend seam.
            max_entries: Optional bound on distinct cached vectors, enforced by
                the underlying :class:`InMemoryDataStore` (evicts the
                least-recently-read vector once full).

        Raises:
            ValueError: If ``max_entries`` is set and less than 1.
        """
        if max_entries is not None and max_entries < 1:
            raise ValueError(
                f"EmbeddingCache: max_entries must be >= 1 or None, got {max_entries!r}"
            )
        self._embed = embed
        self._store = InMemoryDataStore(max_values=max_entries)
        # DataStore exposes no count or enumeration; the live key set answers
        # __len__ and is pruned against the store after every write. The
        # bookkeeping is ``TrackedStoreKeys``, shared with the three caches that
        # were missing the prune (PIR-873).
        self._tracked = TrackedStoreKeys(self._store, bounded=max_entries is not None)
        self.provider_calls = 0
        self.served_from_cache = 0

    def __len__(self) -> int:
        return len(self._tracked)

    @staticmethod
    def key_for(text: str, model: str | None = None) -> str:
        """Return the stable content-hash key for ``text`` under ``model``."""
        return ContentHasher.hash({"text": text, "model": model}, strict=True)

    async def embed(
        self, texts: Sequence[str], *, model: str | None = None
    ) -> list[tuple[float, ...]]:
        """Return one vector per input text, embedding only the cache misses.

        Cached texts skip the provider entirely; the misses are embedded in a
        single batch call (preserving input order) and memoised for next time.

        Args:
            texts: The strings to embed.
            model: Optional model identifier folded into each key so vectors
                from different models never collide.

        Returns:
            One embedding vector (as a tuple) per input string, in input order.

        Raises:
            TypeError: If ``texts`` is a bare ``str`` rather than a sequence.
            ValueError: If the provider returns a vector count that does not
                match the number of texts it was asked to embed.
        """
        if isinstance(texts, str):
            raise TypeError("EmbeddingCache.embed: texts must be a sequence of strings, not a str")
        items = list(texts)
        keys = [self.key_for(text, model) for text in items]
        vectors: dict[str, tuple[float, ...]] = {}
        missing_indices: list[int] = []
        for index, key in enumerate(keys):
            if key in vectors:
                continue
            cached = await self._cached(key)
            if cached is None:
                missing_indices.append(index)
            else:
                vectors[key] = cached

        if missing_indices:
            to_embed = [items[i] for i in missing_indices]
            self.provider_calls += 1
            fresh = await self._embed(to_embed)
            fresh_list = list(fresh)
            if len(fresh_list) != len(to_embed):
                raise ValueError(
                    "EmbeddingCache.embed: provider returned "
                    f"{len(fresh_list)} vectors for {len(to_embed)} texts"
                )
            for index, vector in zip(missing_indices, fresh_list, strict=True):
                key = keys[index]
                vectors[key] = tuple(float(x) for x in vector)
                await self._store.put(key, vectors[key])
                self._tracked.add(key)
            await self._tracked.prune()

        self.served_from_cache += len(items) - len(missing_indices)
        return [vectors[key] for key in keys]

    async def invalidate(self, text: str, *, model: str | None = None) -> None:
        """Drop the cached vector for ``text``/``model`` (a no-op if absent)."""
        key = self.key_for(text, model)
        await self._store.scrub(key)
        self._tracked.discard(key)

    async def _cached(self, key: str) -> tuple[float, ...] | None:
        """Return the stored vector under ``key``, or ``None`` on a miss or eviction."""
        try:
            return await self._store.get(key)
        except (KeyError, ValueEvictedError):
            self._tracked.discard(key)
            return None
