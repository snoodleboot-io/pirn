"""Tests for SubscribableStore interface contract."""

from __future__ import annotations

import unittest

from pirn.backends.base.subscribable_store import SubscribableStore


class TestSubscribableStoreInterface(unittest.TestCase):
    """SubscribableStore is an abstract interface; both methods raise NotImplementedError."""

    def _make_store(self) -> SubscribableStore:
        return SubscribableStore()

    def test_subscribe_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            store.subscribe(lambda knot: None)
        self.assertIn("subscribe()", str(ctx.exception))

    def test_unsubscribe_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            store.unsubscribe(object())
        self.assertIn("unsubscribe()", str(ctx.exception))

    def test_error_message_includes_subclass_name(self) -> None:
        class MyStore(SubscribableStore):
            pass

        store = MyStore()
        with self.assertRaises(NotImplementedError) as ctx:
            store.subscribe(lambda k: None)
        self.assertIn("MyStore", str(ctx.exception))
