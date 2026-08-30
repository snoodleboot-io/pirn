"""Tests for InMemoryDataStore."""

from __future__ import annotations

import unittest

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.exceptions.value_evicted_error import ValueEvictedError


class TestInMemoryDataStore(unittest.IsolatedAsyncioTestCase):
    """InMemoryDataStore: put/get/has/scrub semantics."""

    def setUp(self) -> None:
        self.store = InMemoryDataStore()

    async def test_put_then_get_returns_value(self) -> None:
        await self.store.put("sha256:abc", {"key": "value"})
        result = await self.store.get("sha256:abc")
        self.assertEqual(result, {"key": "value"})

    async def test_has_returns_false_before_put(self) -> None:
        self.assertFalse(await self.store.has("sha256:missing"))

    async def test_has_returns_true_after_put(self) -> None:
        await self.store.put("sha256:x", 42)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")

    async def test_get_key_error_message_contains_hash(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            await self.store.get("sha256:deadbeef")
        self.assertIn("sha256:deadbeef", str(ctx.exception))

    async def test_scrub_removes_value(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_scrub_missing_key_is_idempotent(self) -> None:
        # Must not raise even if key doesn't exist
        await self.store.scrub("sha256:nonexistent")

    async def test_put_overwrites_existing_value(self) -> None:
        await self.store.put("sha256:x", "first")
        await self.store.put("sha256:x", "second")
        result = await self.store.get("sha256:x")
        self.assertEqual(result, "second")

    async def test_multiple_independent_hashes(self) -> None:
        await self.store.put("sha256:a", 1)
        await self.store.put("sha256:b", 2)
        self.assertEqual(await self.store.get("sha256:a"), 1)
        self.assertEqual(await self.store.get("sha256:b"), 2)

    async def test_stores_arbitrary_python_objects(self) -> None:
        obj = [1, 2, {"nested": True}]
        await self.store.put("sha256:x", obj)
        self.assertEqual(await self.store.get("sha256:x"), obj)

    async def test_has_false_after_scrub(self) -> None:
        await self.store.put("sha256:x", 99)
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))


class TestInMemoryDataStoreRetention(unittest.IsolatedAsyncioTestCase):
    """The store keeps a bounded working set and says so (PIR-839)."""

    async def test_default_ceiling_does_not_evict_ordinary_use(self) -> None:
        # Arrange
        store = InMemoryDataStore()

        # Act
        for i in range(200):
            await store.put(f"sha256:{i}", i)

        # Assert
        self.assertEqual(await store.get("sha256:0"), 0)

    async def test_evicts_once_the_ceiling_is_reached(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=3)

        # Act — a fourth write pushes the working set past the ceiling.
        for i in range(4):
            await store.put(f"sha256:{i}", i)

        # Assert
        self.assertFalse(await store.has("sha256:0"))
        for i in (1, 2, 3):
            self.assertEqual(await store.get(f"sha256:{i}"), i)

    async def test_growth_is_bounded_no_matter_how_many_writes(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=4)

        # Act — the open-ended-loop shape: a fresh value every turn, forever.
        for i in range(500):
            await store.put(f"sha256:{i}", i)

        # Assert — the whole point: the footprint does not track the turn count.
        present = [i for i in range(500) if await store.has(f"sha256:{i}")]
        self.assertEqual(len(present), 4)
        self.assertEqual(present, [496, 497, 498, 499])

    async def test_reading_a_value_keeps_it_resident(self) -> None:
        # Arrange — `invariant` is a loop's fixed input: written once, read
        # every turn.  Oldest-first eviction would drop it; LRU must not.
        store = InMemoryDataStore(max_values=3)
        await store.put("sha256:invariant", "keep me")

        # Act
        for i in range(20):
            self.assertEqual(await store.get("sha256:invariant"), "keep me")
            await store.put(f"sha256:turn-{i}", i)

        # Assert
        self.assertTrue(await store.has("sha256:invariant"))

    async def test_has_is_a_probe_and_does_not_refresh_recency(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=2)
        await store.put("sha256:a", 1)
        await store.put("sha256:b", 2)

        # Act — probing `a` must not promote it over `b`.
        self.assertTrue(await store.has("sha256:a"))
        await store.put("sha256:c", 3)

        # Assert
        self.assertFalse(await store.has("sha256:a"))
        self.assertTrue(await store.has("sha256:b"))

    async def test_re_putting_an_evicted_hash_restores_it(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=1)
        await store.put("sha256:a", 1)
        await store.put("sha256:b", 2)

        # Act
        await store.put("sha256:a", 1)

        # Assert — no stale tombstone survives the rewrite.
        self.assertEqual(await store.get("sha256:a"), 1)

    async def test_tombstones_do_not_grow_without_bound(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=4)

        # Act
        for i in range(1_000):
            await store.put(f"sha256:{i}", i)

        # Assert — the record of what was dropped is itself bounded, or it
        # would reintroduce the growth this exists to prevent.
        self.assertLessEqual(len(store._evicted), 4)


class TestInMemoryDataStoreEvictionIsLoud(unittest.IsolatedAsyncioTestCase):
    """An evicted read fails, and says the store let the value go."""

    async def test_reading_an_evicted_value_raises_value_evicted_error(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=1)
        await store.put("sha256:gone", "old")
        await store.put("sha256:kept", "new")

        # Act / Assert
        with self.assertRaises(ValueEvictedError) as ctx:
            await store.get("sha256:gone")
        self.assertEqual(ctx.exception.content_hash, "sha256:gone")
        self.assertEqual(ctx.exception.max_values, 1)

    async def test_value_evicted_error_is_a_key_error(self) -> None:
        # Arrange — the documented DataStore read contract is KeyError, and
        # existing `except KeyError` handlers must keep working.
        store = InMemoryDataStore(max_values=1)
        await store.put("sha256:gone", "old")
        await store.put("sha256:kept", "new")

        # Act / Assert
        with self.assertRaises(KeyError):
            await store.get("sha256:gone")

    async def test_eviction_message_names_the_ceiling(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=1)
        await store.put("sha256:gone", "old")
        await store.put("sha256:kept", "new")

        # Act
        with self.assertRaises(ValueEvictedError) as ctx:
            await store.get("sha256:gone")

        # Assert — a bare `KeyError: 'sha256:gone'` would leave the caller
        # guessing between eviction, a typo and the wrong store.
        message = str(ctx.exception)
        self.assertIn("evicted", message)
        self.assertIn("ceiling of 1", message)
        self.assertNotIn("'sha256:gone'\"", message)

    async def test_a_hash_that_was_never_written_is_a_plain_key_error(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=2)

        # Act / Assert — the two absences have different fixes, so they are
        # not reported as the same thing.
        with self.assertRaises(KeyError) as ctx:
            await store.get("sha256:never")
        self.assertNotIsInstance(ctx.exception, ValueEvictedError)

    async def test_a_scrubbed_value_is_a_plain_key_error(self) -> None:
        # Arrange — scrubbing is the caller's own decision; no ceiling to blame.
        store = InMemoryDataStore(max_values=2)
        await store.put("sha256:x", 1)
        await store.scrub("sha256:x")

        # Act / Assert
        with self.assertRaises(KeyError) as ctx:
            await store.get("sha256:x")
        self.assertNotIsInstance(ctx.exception, ValueEvictedError)

    async def test_a_long_forgotten_eviction_still_fails_just_less_precisely(self) -> None:
        # Arrange — tombstones are bounded too, so the store eventually forgets
        # *why* a hash is gone.  What it must never forget is that it is gone.
        store = InMemoryDataStore(max_values=2)
        await store.put("sha256:ancient", "old")
        for i in range(50):
            await store.put(f"sha256:{i}", i)

        # Act / Assert
        with self.assertRaises(KeyError):
            await store.get("sha256:ancient")

    async def test_eviction_never_returns_a_substitute_value(self) -> None:
        # Arrange
        store = InMemoryDataStore(max_values=1)
        await store.put("sha256:gone", "old")
        await store.put("sha256:kept", "new")

        # Act / Assert — the failure mode this guards against is a read that
        # quietly yields None and is mistaken for a stored value.
        try:
            result = await store.get("sha256:gone")
        except KeyError:
            return
        self.fail(f"evicted read returned {result!r} instead of raising")
