"""Tests for SQLiteStore using real :memory: SQLite."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any
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


class _FailingConnection:
    """Delegates to a real connection but raises on the nth ``execute``.

    Lets a test drive a statement that fails *after* it has already opened a
    transaction, which is what makes the missing rollback observable.
    """

    def __init__(self, connection: sqlite3.Connection, *, fail_on_execute_call: int) -> None:
        self._connection = connection
        self._fail_on_execute_call = fail_on_execute_call
        self.execute_calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        self.execute_calls += 1
        if self.execute_calls == self._fail_on_execute_call:
            # Leave a transaction open behind the failure, exactly as an
            # ``UPDATE ... OR FAIL`` that aborts mid-statement does.
            self._connection.execute("INSERT OR REPLACE INTO knots VALUES (?, ?, ?, ?, ?)", args[1])
            raise RuntimeError("statement failed after opening a transaction")
        return self._connection.execute(*args, **kwargs)


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


class TestSQLiteStoreTransactionOwnership(unittest.TestCase):
    """``register`` ends only the transaction its own statement opened (PIR-823).

    ``SQLiteHistory``'s class docstring recommends sharing one connection
    between the store and the history, so a transaction opened by someone else
    on that connection is documented usage rather than misuse.
    """

    def setUp(self) -> None:
        self._dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._dir, True)
        self.db_path = str(Path(self._dir) / "pirn.db")

    def _initialised_store(self) -> tuple[sqlite3.Connection, SQLiteStore]:
        connection = sqlite3.connect(self.db_path)
        store = SQLiteStore(connection=connection)
        store._ensure_init()
        return connection, store

    def test_register_leaves_a_callers_open_transaction_open(self) -> None:
        connection, store = self._initialised_store()
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE caller_work (v TEXT)")
        connection.commit()

        connection.execute("INSERT INTO caller_work VALUES ('half-written')")
        self.assertTrue(connection.in_transaction)
        store.register(_make_knot("k1"))
        self.assertTrue(connection.in_transaction)

    def test_register_does_not_make_a_callers_rolled_back_work_durable(self) -> None:
        connection, store = self._initialised_store()
        connection.execute("CREATE TABLE caller_work (v TEXT)")
        connection.commit()

        connection.execute("INSERT INTO caller_work VALUES ('half-written')")
        store.register(_make_knot("k1"))
        connection.rollback()
        connection.close()

        reopened = sqlite3.connect(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.execute("SELECT v FROM caller_work").fetchall(), [])

    def test_register_commits_the_transaction_it_opened(self) -> None:
        connection = sqlite3.connect(self.db_path)
        store = SQLiteStore(connection=connection)
        store.register(_make_knot("k1"))
        self.assertFalse(connection.in_transaction)
        connection.close()

        reopened = sqlite3.connect(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.execute("SELECT knot_id FROM knots").fetchall(), [("k1",)])

    def test_register_rolls_back_the_transaction_it_opened_on_failure(self) -> None:
        connection, store = self._initialised_store()
        store._conn = _FailingConnection(connection, fail_on_execute_call=1)

        with self.assertRaises(RuntimeError):
            store.register(_make_knot("k1"))
        self.assertFalse(connection.in_transaction)
        self.assertEqual(connection.execute("SELECT knot_id FROM knots").fetchall(), [])

    def test_snapshot_read_issues_no_commit(self) -> None:
        connection, store = self._initialised_store()
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE caller_work (v TEXT)")
        connection.commit()

        connection.execute("INSERT INTO caller_work VALUES ('uncommitted')")
        store.snapshot()
        self.assertTrue(connection.in_transaction)
