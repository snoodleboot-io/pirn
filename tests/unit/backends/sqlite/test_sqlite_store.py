"""Tests for SQLiteStore using real :memory: SQLite."""

from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import MagicMock

from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.sqlite.sqlite_store import SQLiteStore


def _make_knot(knot_id: str) -> MagicMock:
    knot = MagicMock()
    knot.knot_id = knot_id
    knot.config = MagicMock()
    knot.config.model_dump_json = MagicMock(return_value="{}")
    knot.parents = {}
    return knot


class TestSQLiteStoreRegistration(unittest.TestCase):
    """register / get / all semantics."""

    def setUp(self) -> None:
        self.store = SQLiteStore(path=":memory:")
        self.addCleanup(self.store.close)

    def test_get_returns_none_for_missing(self) -> None:
        self.assertIsNone(self.store.get("missing"))

    def test_register_then_get_returns_knot(self) -> None:
        knot = _make_knot("k1")
        self.store.register(knot)
        self.assertIs(self.store.get("k1"), knot)

    def test_register_same_instance_idempotent(self) -> None:
        knot = _make_knot("k1")
        self.store.register(knot)
        self.store.register(knot)
        self.assertEqual(len(self.store.all()), 1)

    def test_register_different_instance_same_id_raises(self) -> None:
        k1 = _make_knot("k1")
        k2 = _make_knot("k1")
        self.store.register(k1)
        with self.assertRaises(ValueError):
            self.store.register(k2)

    def test_all_empty_initially(self) -> None:
        self.assertEqual(self.store.all(), [])

    def test_all_returns_registered_knots(self) -> None:
        k1 = _make_knot("k1")
        k2 = _make_knot("k2")
        self.store.register(k1)
        self.store.register(k2)
        knots = self.store.all()
        self.assertIn(k1, knots)
        self.assertIn(k2, knots)


class TestSQLiteStoreSnapshot(unittest.TestCase):
    """snapshot() returns the knots persisted to SQLite."""

    def setUp(self) -> None:
        self.store = SQLiteStore(path=":memory:")
        self.addCleanup(self.store.close)

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

    def test_snapshot_comes_from_db_not_live_cache(self) -> None:
        knot = _make_knot("k1")
        self.store.register(knot)
        # Build second store sharing same connection to test DB persistence
        store2 = SQLiteStore(connection=self.store._conn)
        snap = store2.snapshot()
        self.assertIn("k1", snap.knot_ids)


class TestSQLiteStoreSharedConnection(unittest.TestCase):
    """SQLiteStore accepts pre-built sqlite3.Connection."""

    def test_shared_connection_persists_across_instances(self) -> None:
        conn = sqlite3.connect(":memory:")
        store1 = SQLiteStore(connection=conn)
        store2 = SQLiteStore(connection=conn)
        knot = _make_knot("shared-knot")
        store1.register(knot)
        retrieved = store2.get("shared-knot")
        # Both instances share the live dict through same conn
        # store2 won't have the knot in its live dict, but the DB does
        snap = store2.snapshot()
        self.assertIn("shared-knot", snap.knot_ids)


class TestSQLiteStoreInheritance(unittest.TestCase):
    def test_is_tapestry_store_subclass(self) -> None:
        self.assertIsInstance(SQLiteStore(path=":memory:"), TapestryStore)
