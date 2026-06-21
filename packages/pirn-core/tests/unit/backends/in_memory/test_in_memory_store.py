"""Tests for InMemoryStore (TapestryStore + SubscribableStore)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.backends.base.subscribable_store import SubscribableStore
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.in_memory.in_memory_store import InMemoryStore


def _make_knot(knot_id: str) -> MagicMock:
    knot = MagicMock()
    knot.knot_id = knot_id
    return knot


class TestInMemoryStoreRegistration(unittest.TestCase):
    """register / get / all semantics."""

    def setUp(self) -> None:
        self.store = InMemoryStore()

    def test_get_returns_none_for_missing_knot(self) -> None:
        self.assertIsNone(self.store.get("nonexistent"))

    def test_register_then_get_returns_knot(self) -> None:
        knot = _make_knot("k1")
        self.store.register(knot)
        self.assertIs(self.store.get("k1"), knot)

    def test_register_same_instance_idempotent(self) -> None:
        knot = _make_knot("k1")
        self.store.register(knot)
        self.store.register(knot)  # must not raise
        self.assertEqual(len(self.store.all()), 1)

    def test_register_different_instance_same_id_raises(self) -> None:
        k1 = _make_knot("k1")
        k2 = _make_knot("k1")
        self.store.register(k1)
        with self.assertRaises(ValueError):
            self.store.register(k2)

    def test_all_returns_empty_initially(self) -> None:
        self.assertEqual(self.store.all(), [])

    def test_all_returns_registered_knots(self) -> None:
        k1 = _make_knot("k1")
        k2 = _make_knot("k2")
        self.store.register(k1)
        self.store.register(k2)
        knots = self.store.all()
        self.assertIn(k1, knots)
        self.assertIn(k2, knots)

    def test_all_returns_copy_not_internal_dict(self) -> None:
        k1 = _make_knot("k1")
        self.store.register(k1)
        result = self.store.all()
        result.clear()
        self.assertEqual(len(self.store.all()), 1)


class TestInMemoryStoreSnapshot(unittest.TestCase):
    """snapshot() returns a frozen TapestrySnapshot."""

    def setUp(self) -> None:
        self.store = InMemoryStore()

    def test_snapshot_empty(self) -> None:
        snap = self.store.snapshot()
        self.assertIsInstance(snap, TapestrySnapshot)
        self.assertEqual(snap.knot_ids, [])

    def test_snapshot_includes_registered_ids(self) -> None:
        self.store.register(_make_knot("a"))
        self.store.register(_make_knot("b"))
        snap = self.store.snapshot()
        self.assertIn("a", snap.knot_ids)
        self.assertIn("b", snap.knot_ids)

    def test_snapshot_does_not_reflect_later_mutations(self) -> None:
        snap = self.store.snapshot()
        self.store.register(_make_knot("new"))
        self.assertNotIn("new", snap.knot_ids)


class TestInMemoryStoreSubscription(unittest.TestCase):
    """subscribe / unsubscribe callbacks."""

    def setUp(self) -> None:
        self.store = InMemoryStore()

    def test_subscribe_returns_token(self) -> None:
        token = self.store.subscribe(lambda k: None)
        self.assertIsNotNone(token)

    def test_callback_called_on_new_registration(self) -> None:
        received: list[MagicMock] = []
        self.store.subscribe(received.append)
        knot = _make_knot("k1")
        self.store.register(knot)
        self.assertEqual(len(received), 1)
        self.assertIs(received[0], knot)

    def test_callback_not_called_for_re_registration_same_instance(self) -> None:
        received: list[MagicMock] = []
        knot = _make_knot("k1")
        self.store.register(knot)
        self.store.subscribe(received.append)
        self.store.register(knot)
        self.assertEqual(received, [])

    def test_unsubscribe_stops_callbacks(self) -> None:
        received: list[MagicMock] = []
        token = self.store.subscribe(received.append)
        self.store.unsubscribe(token)
        self.store.register(_make_knot("k1"))
        self.assertEqual(received, [])

    def test_multiple_subscribers_all_notified(self) -> None:
        calls_a: list[MagicMock] = []
        calls_b: list[MagicMock] = []
        self.store.subscribe(calls_a.append)
        self.store.subscribe(calls_b.append)
        self.store.register(_make_knot("k1"))
        self.assertEqual(len(calls_a), 1)
        self.assertEqual(len(calls_b), 1)

    def test_callback_exception_does_not_propagate(self) -> None:
        def _bad_cb(knot: MagicMock) -> None:
            raise RuntimeError("subscriber error")

        self.store.subscribe(_bad_cb)
        # Must not raise
        self.store.register(_make_knot("k1"))

    def test_unsubscribe_unknown_token_is_idempotent(self) -> None:
        self.store.unsubscribe(9999)  # must not raise


class TestInMemoryStoreInheritance(unittest.TestCase):
    """InMemoryStore inherits from both TapestryStore and SubscribableStore."""

    def test_is_instance_of_tapestry_store(self) -> None:
        self.assertIsInstance(InMemoryStore(), TapestryStore)

    def test_is_instance_of_subscribable_store(self) -> None:
        self.assertIsInstance(InMemoryStore(), SubscribableStore)
