"""Mirrored tests for :class:`InMemoryResultCache` hit/miss/invalidation (PIR-292, PIR-872)."""

from __future__ import annotations

import pytest
from pirn.core.hashing import content_hash

from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache


async def _one() -> int:
    return 1


class TestCounters:
    async def test_miss_then_hit(self) -> None:
        cache = InMemoryResultCache()
        assert await cache.get_or_compute("k", _one) == 1
        assert cache.misses == 1
        assert await cache.get_or_compute("k", _one) == 1
        assert cache.hits == 1

    async def test_invalidate_removes_entry(self) -> None:
        cache = InMemoryResultCache()
        await cache.get_or_compute("k", _one)
        key = content_hash("k", strict=True)
        await cache.invalidate(key)
        assert await cache.store.has(key) is False
        assert len(cache) == 0

    async def test_invalidate_absent_key_is_noop(self) -> None:
        cache = InMemoryResultCache()
        await cache.invalidate("nope")  # no raise


class TestBounding:
    def test_rejects_bad_max_entries(self) -> None:
        with pytest.raises(ValueError, match="max_entries"):
            InMemoryResultCache(max_entries=0)

    async def test_eviction_at_bound(self) -> None:
        cache = InMemoryResultCache(max_entries=2)
        await cache.get_or_compute("a", _one)
        await cache.get_or_compute("b", _one)
        await cache.get_or_compute("c", _one)  # evicts "a"
        assert await cache.store.has(content_hash("a", strict=True)) is False
        assert await cache.store.has(content_hash("b", strict=True)) is True
        assert await cache.store.has(content_hash("c", strict=True)) is True

    async def test_recomputing_an_existing_key_does_not_grow(self) -> None:
        cache = InMemoryResultCache(max_entries=2)
        await cache.get_or_compute("a", _one)
        await cache.get_or_compute("b", _one)
        await cache.get_or_compute("a", _one)  # hit, not insert
        assert len(cache) == 2


class TestGetOrCompute:
    async def test_idempotent_call_hits_on_repeat(self) -> None:
        cache = InMemoryResultCache()
        calls = 0

        async def compute() -> str:
            nonlocal calls
            calls += 1
            return "result"

        payload = {"tool": "search", "args": {"q": "x"}}
        first = await cache.get_or_compute(payload, compute)
        second = await cache.get_or_compute(payload, compute)
        assert first == second == "result"
        assert calls == 1  # second call served from cache

    async def test_different_inputs_recompute(self) -> None:
        cache = InMemoryResultCache()
        calls = 0

        async def compute() -> int:
            nonlocal calls
            calls += 1
            return calls

        await cache.get_or_compute({"q": "a"}, compute)
        await cache.get_or_compute({"q": "b"}, compute)
        assert calls == 2

    async def test_embedding_lookup_memoised(self) -> None:
        cache = InMemoryResultCache()
        embed_calls = 0

        async def embed() -> tuple[float, ...]:
            nonlocal embed_calls
            embed_calls += 1
            return (0.1, 0.2, 0.3)

        vec1 = await cache.get_or_compute("hello", embed)
        vec2 = await cache.get_or_compute("hello", embed)
        assert vec1 == vec2 == (0.1, 0.2, 0.3)
        assert embed_calls == 1
