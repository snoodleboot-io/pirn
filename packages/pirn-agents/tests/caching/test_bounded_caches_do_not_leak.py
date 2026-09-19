"""A bounded cache's bookkeeping must not outgrow the store it mirrors.

``DataStore`` is keyed lookup only, so each cache keeps its own set of the keys
it has written to answer ``len()``/``asize()`` and to walk entries for expiry.
A bounded store evicts *silently*, and three of the four caches only dropped a
key when that same key was next looked up and missed — so the key set, and the
similarity index scanned on every semantic lookup, grew for the life of the
process while the store held at most ``max_entries`` values, and the reported
size was "keys ever written" rather than "entries retrievable" (PIR-873).

Every one of these fails on the old code: the reported size was the number of
writes.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.caching.embedding_cache import EmbeddingCache
from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache
from pirn_agents.caching.prompt_cache import PromptCache
from pirn_agents.caching.semantic_result_cache import SemanticResultCache


async def _one() -> int:
    """A compute callable for a cache miss."""
    return 1


class _SpreadEmbedder:
    """A deterministic embedder giving every distinct text its own direction."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, text: str) -> Sequence[float]:
        self.calls += 1
        seed = sum(ord(ch) for ch in text)
        return (float(seed % 7), float(seed % 11), float(seed % 13))


class _StubBatchEmbedder:
    """A batch embedder giving every text a distinct vector."""

    async def __call__(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [(float(len(text)), float(index)) for index, text in enumerate(texts)]


class TestInMemoryResultCache:
    async def test_len_counts_what_is_retrievable_not_what_was_written(self) -> None:
        # Arrange
        cache = InMemoryResultCache(max_entries=2)

        # Act — ten distinct payloads into a store that holds two.
        for index in range(10):
            await cache.get_or_compute({"payload": index}, _one)

        # Assert
        assert len(cache) == 2

    async def test_an_unbounded_cache_still_counts_every_entry(self) -> None:
        cache = InMemoryResultCache()
        for index in range(10):
            await cache.get_or_compute({"payload": index}, _one)
        assert len(cache) == 10


class TestSemanticResultCache:
    async def test_both_the_key_set_and_the_similarity_index_stay_bounded(self) -> None:
        # Arrange
        cache = SemanticResultCache(embed=_SpreadEmbedder(), threshold=0.999, max_entries=2)

        # Act
        for index in range(10):
            await cache.get_or_compute_semantic(f"query-{index}", _one)

        # Assert — the index is scanned on every semantic lookup, so a leak
        # there is a growing cost per call, not just a wrong number.
        assert len(cache) == 2
        assert len(cache._index) == 2

    async def test_an_unbounded_cache_still_counts_every_entry(self) -> None:
        cache = SemanticResultCache(embed=_SpreadEmbedder(), threshold=0.999)
        for index in range(10):
            await cache.get_or_compute_semantic(f"query-{index}", _one)
        assert len(cache) == 10


class TestPromptCache:
    async def test_asize_counts_what_is_retrievable_not_what_was_written(self) -> None:
        # Arrange
        cache = PromptCache(max_entries=2)

        # Act
        for index in range(10):
            await cache.get_or_compute(f"prompt-{index}", _one)

        # Assert
        assert await cache.asize() == 2

    async def test_the_similarity_index_stays_bounded_too(self) -> None:
        # Arrange
        cache = PromptCache(embed=_SpreadEmbedder(), threshold=0.999, max_entries=2)

        # Act
        for index in range(10):
            await cache.get_or_compute(f"prompt-{index}", _one)

        # Assert
        assert await cache.asize() == 2
        assert len(cache._index) == 2

    async def test_an_unbounded_cache_still_counts_every_entry(self) -> None:
        cache = PromptCache()
        for index in range(10):
            await cache.get_or_compute(f"prompt-{index}", _one)
        assert await cache.asize() == 10


class TestEmbeddingCache:
    async def test_stays_bounded_as_it_already_did(self) -> None:
        """The cache that had the prune: a regression guard now the prune is shared."""
        cache = EmbeddingCache(_StubBatchEmbedder(), max_entries=2)
        for index in range(10):
            await cache.embed([f"text-{index}"])
        assert len(cache) == 2

    async def test_an_unbounded_cache_still_counts_every_entry(self) -> None:
        cache = EmbeddingCache(_StubBatchEmbedder())
        for index in range(10):
            await cache.embed([f"text-{index}"])
        assert len(cache) == 10
