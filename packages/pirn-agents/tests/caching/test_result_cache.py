"""Contract tests for the :class:`ResultCache` base class (ADR agents-speaks-core WS2, PIR-872).

``ResultCache`` composes a core ``DataStore`` and adds only compute-on-miss
memoisation (:meth:`ResultCache.get_or_compute`) and :meth:`ResultCache.invalidate`;
raw keyed access is the store itself (:attr:`ResultCache.store`), so the cache is
not a second keyed-store surface beside ``DataStore``.
"""

from __future__ import annotations

import functools
import unittest
from collections.abc import Awaitable, Callable

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.core.content_hasher import ContentHasher

from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache
from pirn_agents.caching.result_cache import ResultCache
from pirn_agents.caching.semantic_result_cache import SemanticResultCache


class TestResultCacheContract(unittest.IsolatedAsyncioTestCase):
    def test_concrete_caches_subclass_base(self) -> None:
        self.assertTrue(issubclass(InMemoryResultCache, ResultCache))
        self.assertTrue(issubclass(SemanticResultCache, ResultCache))

    def test_the_cache_exposes_no_keyed_store_surface_of_its_own(self) -> None:
        for name in ("get", "put", "has"):
            self.assertFalse(hasattr(ResultCache, name), name)

    async def test_values_live_in_the_given_store(self) -> None:
        store = InMemoryDataStore()
        cache = ResultCache(store=store)

        value = await cache.get_or_compute({"q": "x"}, _resolved(7))

        self.assertIs(cache.store, store)
        key = ContentHasher.hash({"q": "x"}, strict=True)
        self.assertTrue(await store.has(key))
        self.assertEqual((await store.get(key)).value, value)

    async def test_invalidate_scrubs_the_store(self) -> None:
        store = InMemoryDataStore()
        cache = ResultCache(store=store)
        await cache.get_or_compute("p", _resolved(1))
        key = ContentHasher.hash("p", strict=True)

        await cache.invalidate(key)

        self.assertFalse(await store.has(key))

    async def test_evicted_value_is_recomputed_not_an_error(self) -> None:
        # A cache is optional by construction: an evicted result is simply
        # recomputed, so get_or_compute must never surface ValueEvictedError.
        cache = ResultCache(store=InMemoryDataStore(max_values=1))
        calls: list[str] = []

        async def compute_a() -> str:
            calls.append("a")
            return "a"

        await cache.get_or_compute("a", compute_a)
        await cache.get_or_compute("b", _resolved("b"))  # evicts "a"
        await cache.get_or_compute("a", compute_a)

        self.assertEqual(calls, ["a", "a"])


async def _constant(value: object) -> object:
    return value


def _resolved(value: object) -> Callable[[], Awaitable[object]]:
    return functools.partial(_constant, value)


if __name__ == "__main__":
    unittest.main()
