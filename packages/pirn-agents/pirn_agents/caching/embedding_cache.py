"""``EmbeddingCache`` — memoise embedding vectors by content hash across providers.

Embedding the same text twice is pure waste: the vector is a deterministic
function of ``(text, model)``. This cache keys each text by its
:func:`~pirn_agents.caching.content_address.content_address` (folding in the
model so different models never collide) and only calls the wrapped embed
function for texts it has never seen. Re-indexing an overlapping corpus therefore
collapses to embedding just the *new* texts — the counters
:attr:`provider_calls` and :attr:`served_from_cache` make that saving
measurable.

The wrapped embed function is the sole backend seam — any
:class:`pirn_agents.embedding_provider.EmbeddingProvider` ``embed`` (or a
plain async callable) fits — so the cache is provider-neutral and no vendor SDK
is imported here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from pirn_agents.caching.content_address import content_address


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
            max_entries: Optional FIFO bound on distinct cached vectors.

        Raises:
            ValueError: If ``max_entries`` is set and less than 1.
        """
        if max_entries is not None and max_entries < 1:
            raise ValueError(
                f"EmbeddingCache: max_entries must be >= 1 or None, got {max_entries!r}"
            )
        self._embed = embed
        self._max_entries = max_entries
        self._vectors: dict[str, tuple[float, ...]] = {}
        self.provider_calls = 0
        self.served_from_cache = 0

    def __len__(self) -> int:
        return len(self._vectors)

    @staticmethod
    def key_for(text: str, model: str | None = None) -> str:
        """Return the stable content-hash key for ``text`` under ``model``."""
        return content_address({"text": text, "model": model})

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
        missing_indices = [i for i, key in enumerate(keys) if key not in self._vectors]

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
                self._store(keys[index], tuple(float(x) for x in vector))

        self.served_from_cache += len(items) - len(missing_indices)
        return [self._vectors[key] for key in keys]

    def invalidate(self, text: str, *, model: str | None = None) -> None:
        """Drop the cached vector for ``text``/``model`` (a no-op if absent)."""
        self._vectors.pop(self.key_for(text, model), None)

    def _store(self, key: str, vector: tuple[float, ...]) -> None:
        """Insert ``vector`` under ``key`` with optional FIFO eviction."""
        if (
            self._max_entries is not None
            and key not in self._vectors
            and len(self._vectors) >= self._max_entries
        ):
            del self._vectors[next(iter(self._vectors))]
        self._vectors[key] = vector
