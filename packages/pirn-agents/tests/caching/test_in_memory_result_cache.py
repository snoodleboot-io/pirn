"""Mirrored tests for :class:`InMemoryResultCache` hit/miss/invalidation (PIR-292)."""

from __future__ import annotations

import pytest

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache


class TestGetPut:
    async def test_miss_then_hit(self) -> None:
        cache = InMemoryResultCache()
        assert await cache.get("k") is None
        assert cache.misses == 1
        await cache.put(CacheEntry(key="k", value="v"))
        entry = await cache.get("k")
        assert entry is not None and entry.value == "v"
        assert cache.hits == 1

    async def test_invalidate_removes_entry(self) -> None:
        cache = InMemoryResultCache()
        await cache.put(CacheEntry(key="k", value=1))
        await cache.invalidate("k")
        assert await cache.get("k") is None

    async def test_invalidate_absent_key_is_noop(self) -> None:
        cache = InMemoryResultCache()
        await cache.invalidate("nope")  # no raise


class TestBounding:
    def test_rejects_bad_max_entries(self) -> None:
        with pytest.raises(ValueError, match="max_entries"):
            InMemoryResultCache(max_entries=0)

    async def test_fifo_eviction_at_bound(self) -> None:
        cache = InMemoryResultCache(max_entries=2)
        await cache.put(CacheEntry(key="a", value=1))
        await cache.put(CacheEntry(key="b", value=2))
        await cache.put(CacheEntry(key="c", value=3))  # evicts "a"
        assert await cache.get("a") is None
        assert (await cache.get("b")) is not None
        assert (await cache.get("c")) is not None
        assert len(cache) == 2

    async def test_overwrite_existing_does_not_evict(self) -> None:
        cache = InMemoryResultCache(max_entries=2)
        await cache.put(CacheEntry(key="a", value=1))
        await cache.put(CacheEntry(key="b", value=2))
        await cache.put(CacheEntry(key="a", value=99))  # update, not insert
        assert len(cache) == 2
        entry = await cache.get("a")
        assert entry is not None and entry.value == 99


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
