"""Tests for PostgresStore using a fully-mocked asyncpg pool."""

from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends.base.subscribable_store import SubscribableStore
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.postgres.postgres_store import PostgresStore


def _make_knot(knot_id: str) -> MagicMock:
    knot = MagicMock()
    knot.knot_id = knot_id
    knot.config = MagicMock()
    knot.config.model_dump_json = MagicMock(return_value="{}")
    knot.parents = {}
    return knot


class _FakePool:
    def __init__(self) -> None:
        self._knots: dict[str, dict] = {}
        self._schema_version: dict[str, int] = {}

    @asynccontextmanager
    async def acquire(self) -> Any:
        yield _FakeConn(self)

    async def close(self) -> None:
        pass


class _FakeConn:
    def __init__(self, pool: _FakePool) -> None:
        self._pool = pool

    async def execute(self, sql: str, *args: Any) -> None:
        if "INSERT INTO knots" in sql or "INSERT INTO pirn_schema_version" in sql:
            if "pirn_schema_version" in sql and "INSERT" in sql:
                component, version = args[0], args[1]
                self._pool._schema_version[component] = version
            elif "INSERT INTO knots" in sql:
                knot_id = args[0]
                self._pool._knots[knot_id] = {"knot_id": knot_id}
        elif "CREATE TABLE" in sql or "ALTER TABLE" in sql or "CREATE INDEX" in sql:
            pass
        elif "SELECT pg_notify" in sql:
            pass

    async def fetchrow(self, sql: str, *args: Any) -> Any | None:
        if "pirn_schema_version" in sql:
            component = args[0]
            v = self._pool._schema_version.get(component)
            return {"version": v} if v is not None else None
        return None

    async def add_listener(self, channel: str, cb: Any) -> None:
        pass

    async def remove_listener(self, channel: str, cb: Any) -> None:
        pass


def _make_store() -> PostgresStore:
    fake_pool = _FakePool()
    return PostgresStore(pool=fake_pool)


class TestPostgresStoreConstruction(unittest.TestCase):
    def test_requires_pool_or_dsn(self) -> None:
        with self.assertRaises(TypeError):
            PostgresStore()

    def test_accepts_injected_pool(self) -> None:
        store = _make_store()
        self.assertIsNotNone(store)


class TestPostgresStoreLiveOperations(unittest.TestCase):
    """get / all / snapshot use in-process live dict."""

    def setUp(self) -> None:
        self.store = _make_store()

    def test_get_returns_none_initially(self) -> None:
        self.assertIsNone(self.store.get("missing"))

    def test_all_empty_initially(self) -> None:
        self.assertEqual(self.store.all(), [])

    def test_snapshot_empty_initially(self) -> None:
        snap = self.store.snapshot()
        self.assertIsInstance(snap, TapestrySnapshot)
        self.assertEqual(snap.knot_ids, [])

    def test_register_different_instance_same_id_raises(self) -> None:
        k1 = _make_knot("k1")
        k2 = _make_knot("k1")
        self.store._live["k1"] = k1
        with self.assertRaises(ValueError):
            import asyncio
            asyncio.run(self.store.aregister(k2))


class TestPostgresStoreAsyncRegister(unittest.IsolatedAsyncioTestCase):
    async def test_aregister_stores_in_live_dict(self) -> None:
        store = _make_store()
        knot = _make_knot("k1")
        await store.aregister(knot)
        self.assertIs(store.get("k1"), knot)
        self.assertIn(knot, store.all())

    async def test_aregister_idempotent_for_same_instance(self) -> None:
        store = _make_store()
        knot = _make_knot("k1")
        await store.aregister(knot)
        await store.aregister(knot)  # must not raise

    async def test_aregister_updates_snapshot(self) -> None:
        store = _make_store()
        knot = _make_knot("k1")
        await store.aregister(knot)
        snap = store.snapshot()
        self.assertIn("k1", snap.knot_ids)


class TestPostgresStoreSubscription(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = _make_store()

    async def test_subscribe_returns_token(self) -> None:
        token = self.store.subscribe(lambda k: None)
        self.assertIsNotNone(token)

    async def test_unsubscribe_removes_callback(self) -> None:
        token = self.store.subscribe(lambda k: None)
        self.store.unsubscribe(token)
        self.assertNotIn(token, self.store._subscribers)

    def test_unsubscribe_unknown_token_is_idempotent(self) -> None:
        self.store.unsubscribe(9999)


class TestPostgresStoreOnNotify(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _make_store()

    def test_on_notify_dispatches_to_subscriber(self) -> None:
        knot = _make_knot("k1")
        self.store._live["k1"] = knot
        received: list = []
        self.store._subscribers[0] = received.append
        self.store._on_notify(None, 1234, "pirn_knots", "k1")
        self.assertEqual(received, [knot])

    def test_on_notify_ignores_unknown_knot(self) -> None:
        received: list = []
        self.store._subscribers[0] = received.append
        self.store._on_notify(None, 1234, "pirn_knots", "unknown")
        self.assertEqual(received, [])

    def test_on_notify_subscriber_exception_does_not_propagate(self) -> None:
        knot = _make_knot("k1")
        self.store._live["k1"] = knot

        def _bad(k: Any) -> None:
            raise RuntimeError("boom")

        self.store._subscribers[0] = _bad
        self.store._on_notify(None, 1234, "pirn_knots", "k1")  # must not raise


class TestPostgresStoreInheritance(unittest.TestCase):
    def test_is_tapestry_store(self) -> None:
        self.assertIsInstance(_make_store(), TapestryStore)

    def test_is_subscribable_store(self) -> None:
        self.assertIsInstance(_make_store(), SubscribableStore)
