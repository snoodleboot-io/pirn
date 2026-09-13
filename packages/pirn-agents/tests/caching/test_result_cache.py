"""Contract tests for the :class:`ResultCache` base class (ADR agents-speaks-core WS2).

Was WS1·S5's house-interface style (a plain base whose storage methods raise
``NotImplementedError``, with concrete caches subclassing it) over a private
dict. The ADR retired the private dict: ``ResultCache`` now composes a core
``DataStore`` directly and is concrete, so these tests lock in the new
contract — a bare ``ResultCache`` wraps whatever store it is given, and
:class:`InMemoryResultCache` is a thin default over
:class:`~pirn.backends.in_memory.in_memory_data_store.InMemoryDataStore`.
"""

from __future__ import annotations

import unittest

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache
from pirn_agents.caching.result_cache import ResultCache
from pirn_agents.caching.semantic_result_cache import SemanticResultCache


class TestResultCacheContract(unittest.IsolatedAsyncioTestCase):
    def test_concrete_caches_subclass_base(self) -> None:
        # Arrange / Act / Assert: both backends declare the base nominally.
        self.assertTrue(issubclass(InMemoryResultCache, ResultCache))
        self.assertTrue(issubclass(SemanticResultCache, ResultCache))

    async def test_bare_cache_is_thin_over_its_store(self) -> None:
        # Arrange: a bare ResultCache wrapping a store directly (no subclass).
        cache = ResultCache(store=InMemoryDataStore())

        # Act / Assert: get/put/has/invalidate all reach the store.
        self.assertIsNone(await cache.get("k"))
        self.assertFalse(await cache.has("k"))
        await cache.put(CacheEntry(key="k", value=1, embedding=None))
        self.assertTrue(await cache.has("k"))
        entry = await cache.get("k")
        assert entry is not None
        self.assertEqual(entry.value, 1)
        await cache.invalidate("k")
        self.assertIsNone(await cache.get("k"))

    async def test_evicted_value_reads_as_a_miss_not_an_error(self) -> None:
        # A cache is optional by construction: an evicted result is simply
        # recomputed, so ResultCache.get must never surface ValueEvictedError.
        cache = ResultCache(store=InMemoryDataStore(max_values=1))
        await cache.put(CacheEntry(key="a", value=1))
        await cache.put(CacheEntry(key="b", value=2))  # evicts "a"
        self.assertIsNone(await cache.get("a"))


if __name__ == "__main__":
    unittest.main()
