"""Mirrored tests for :class:`EmbeddingCache` content-hash memoisation (PIR-501).

A stub batch embedder (no vendor backend) counts how many texts actually reach
the provider, so the "re-indexing skips redundant calls" acceptance criterion is
asserted directly and reproducibly.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pirn_agents.caching.embedding_cache import EmbeddingCache


class _StubBatchEmbedder:
    """Deterministic embedder recording every batch it is asked to embed."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    async def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        batch = list(texts)
        self.batches.append(batch)
        return [[float(len(t)), 1.0] for t in batch]

    @property
    def texts_embedded(self) -> int:
        return sum(len(b) for b in self.batches)


class TestValidation:
    def test_bad_max_entries_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_entries"):
            EmbeddingCache(_StubBatchEmbedder(), max_entries=0)

    async def test_bare_str_rejected(self) -> None:
        cache = EmbeddingCache(_StubBatchEmbedder())
        with pytest.raises(TypeError, match="sequence"):
            await cache.embed("oops")  # type: ignore[arg-type]

    async def test_provider_count_mismatch_raises(self) -> None:
        async def bad(texts: Sequence[str]) -> list[list[float]]:
            return []  # wrong length

        cache = EmbeddingCache(bad)
        with pytest.raises(ValueError, match="vectors for"):
            await cache.embed(["a"])


class TestMemoisation:
    async def test_hit_skips_provider(self) -> None:
        stub = _StubBatchEmbedder()
        cache = EmbeddingCache(stub)

        first = await cache.embed(["alpha", "beta"])
        second = await cache.embed(["alpha", "beta"])

        assert first == second
        assert stub.texts_embedded == 2  # second call embedded nothing
        assert cache.provider_calls == 1
        assert cache.served_from_cache == 2

    async def test_partial_overlap_embeds_only_new_texts(self) -> None:
        stub = _StubBatchEmbedder()
        cache = EmbeddingCache(stub)

        await cache.embed(["a", "b"])
        await cache.embed(["b", "c"])  # only "c" is new

        assert stub.texts_embedded == 3  # a, b, then c
        assert stub.batches[1] == ["c"]

    async def test_reindexing_corpus_reduces_calls(self) -> None:
        stub = _StubBatchEmbedder()
        cache = EmbeddingCache(stub)
        corpus = ["doc-1", "doc-2", "doc-3"]

        await cache.embed(corpus)
        await cache.embed(corpus)  # full re-index

        assert stub.texts_embedded == 3  # measurable: second index cost nothing
        assert cache.served_from_cache == 3

    async def test_model_partitions_keys(self) -> None:
        stub = _StubBatchEmbedder()
        cache = EmbeddingCache(stub)

        await cache.embed(["x"], model="small")
        await cache.embed(["x"], model="large")

        assert stub.texts_embedded == 2  # same text, different model -> no collision

    async def test_order_preserved_across_mixed_hits(self) -> None:
        stub = _StubBatchEmbedder()
        cache = EmbeddingCache(stub)

        await cache.embed(["short", "muchlongertext"])
        out = await cache.embed(["muchlongertext", "short"])

        assert out[0][0] == float(len("muchlongertext"))
        assert out[1][0] == float(len("short"))


class TestEvictionAndInvalidate:
    async def test_invalidate_forces_recompute(self) -> None:
        stub = _StubBatchEmbedder()
        cache = EmbeddingCache(stub)

        await cache.embed(["k"])
        cache.invalidate("k")
        await cache.embed(["k"])

        assert stub.texts_embedded == 2

    async def test_fifo_bound(self) -> None:
        stub = _StubBatchEmbedder()
        cache = EmbeddingCache(stub, max_entries=1)

        await cache.embed(["one"])
        await cache.embed(["two"])

        assert len(cache) == 1
