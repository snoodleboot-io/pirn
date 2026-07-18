"""Contract tests for the :class:`ResultCache` base class (WS1·S5).

Locks in the house interface style: a plain base class whose storage methods
raise ``NotImplementedError`` (not ``abc``/``@abstractmethod``), with the
concrete caches subclassing it.
"""

from __future__ import annotations

import unittest

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache
from pirn_agents.caching.result_cache import ResultCache
from pirn_agents.caching.semantic_result_cache import SemanticResultCache


class TestResultCacheContract(unittest.IsolatedAsyncioTestCase):
    def test_concrete_caches_subclass_base(self) -> None:
        # Arrange / Act / Assert: both backends declare the base nominally.
        self.assertTrue(issubclass(InMemoryResultCache, ResultCache))
        self.assertTrue(issubclass(SemanticResultCache, ResultCache))

    async def test_base_methods_raise_not_implemented(self) -> None:
        # Arrange: a bare base instance (interface style — instantiable, no abc).
        cache = ResultCache()

        # Act / Assert: every storage method reports the owning class.
        with self.assertRaisesRegex(NotImplementedError, "ResultCache"):
            await cache.get("k")
        with self.assertRaisesRegex(NotImplementedError, "ResultCache"):
            await cache.put(CacheEntry(key="k", value=1, embedding=None))
        with self.assertRaisesRegex(NotImplementedError, "ResultCache"):
            await cache.invalidate("k")


if __name__ == "__main__":
    unittest.main()
