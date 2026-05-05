"""Tests for TapestryStore interface contract."""

from __future__ import annotations

import unittest

from pirn.backends.base.tapestry_store import TapestryStore


class TestTapestryStoreInterface(unittest.TestCase):
    """TapestryStore is an abstract interface; all methods raise NotImplementedError."""

    def _make_store(self) -> TapestryStore:
        return TapestryStore()

    def test_register_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            store.register(object())  # type: ignore[arg-type]
        self.assertIn("register()", str(ctx.exception))

    def test_get_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            store.get("knot-1")
        self.assertIn("get()", str(ctx.exception))

    def test_all_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            store.all()
        self.assertIn("all()", str(ctx.exception))

    def test_snapshot_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            store.snapshot()
        self.assertIn("snapshot()", str(ctx.exception))

    def test_error_message_includes_subclass_name(self) -> None:
        class MyStore(TapestryStore):
            pass

        store = MyStore()
        with self.assertRaises(NotImplementedError) as ctx:
            store.all()
        self.assertIn("MyStore", str(ctx.exception))
