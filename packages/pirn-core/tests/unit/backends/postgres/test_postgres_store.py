"""Tests for PostgresStore using a fully-mocked asyncpg pool."""

from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock

from pirn.backends.base.knot_registration_notice import KnotRegistrationNotice
from pirn.backends.base.subscribable_store import SubscribableStore
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.postgres.postgres_store import PostgresStore
from pirn.engine._run_scoped_subscriber import _RunScopedSubscriber
from pirn.tapestry import _current_run_id, current_run_id


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
        #: Payloads handed to ``pg_notify``, in send order.  A real LISTEN
        #: task reads these back from the server; the tests replay them
        #: into ``_on_notify`` to model that hop.
        self.notifications: list[str] = []

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
            self._pool.notifications.append(args[0])

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


class TestPostgresStoreRunAttribution(unittest.IsolatedAsyncioTestCase):
    """NOTIFY payloads carry the registering run, and delivery restores it.

    ``PostgresStore`` delivers through a background LISTEN task, which
    never inherited the registering task's context, so PIR-808's
    ``_RunScopedSubscriber`` saw no ambient run and fell through its
    ``None`` passthrough -- every extensible run on the tapestry got
    every other run's knots (PIR-815).
    """

    def setUp(self) -> None:
        self.pool = _FakePool()
        self.store = PostgresStore(pool=self.pool)

    async def _register_under_run(self, knot: Any, run_id: str | None) -> None:
        """Register ``knot`` with ``run_id`` as the ambient run, then leave.

        Mirrors the real shape: the registration happens inside the run's
        context, the notification is read back somewhere else entirely.
        """
        token = _current_run_id.set(run_id)
        try:
            await self.store.aregister(knot)
        finally:
            _current_run_id.reset(token)

    def _drain_notifications(self) -> None:
        """Replay captured payloads the way the LISTEN task would.

        Deliberately called with no run in scope -- that is exactly what
        the background task's context looks like.
        """
        self.assertIsNone(current_run_id())
        for payload in self.pool.notifications:
            self.store._on_notify(None, 1234, "pirn_knots", payload)
        self.pool.notifications.clear()

    async def test_notify_payload_carries_the_registering_run_id(self) -> None:
        self.store._subscribers[0] = lambda k: None
        await self._register_under_run(_make_knot("k1"), "run-a")

        self.assertEqual(len(self.pool.notifications), 1)
        notice = KnotRegistrationNotice.decode(self.pool.notifications[0])
        self.assertEqual(notice.knot_id, "k1")
        self.assertEqual(notice.run_id, "run-a")

    async def test_concurrent_runs_do_not_receive_each_others_knots(self) -> None:
        pending_a: list[Any] = []
        pending_b: list[Any] = []
        self.store._subscribers[0] = _RunScopedSubscriber("run-a", pending_a)
        self.store._subscribers[1] = _RunScopedSubscriber("run-b", pending_b)

        knot_a = _make_knot("k-a")
        knot_b = _make_knot("k-b")
        await self._register_under_run(knot_a, "run-a")
        await self._register_under_run(knot_b, "run-b")
        self._drain_notifications()

        self.assertEqual(pending_a, [knot_a])
        self.assertEqual(pending_b, [knot_b])

    async def test_delivery_runs_under_the_registering_run(self) -> None:
        seen: list[str | None] = []
        self.store._subscribers[0] = lambda k: seen.append(current_run_id())
        await self._register_under_run(_make_knot("k1"), "run-a")
        self._drain_notifications()

        self.assertEqual(seen, ["run-a"])

    async def test_registration_with_no_run_in_scope_still_broadcasts(self) -> None:
        pending_a: list[Any] = []
        pending_b: list[Any] = []
        self.store._subscribers[0] = _RunScopedSubscriber("run-a", pending_a)
        self.store._subscribers[1] = _RunScopedSubscriber("run-b", pending_b)

        knot = _make_knot("k1")
        await self._register_under_run(knot, None)
        self._drain_notifications()

        # PIR-808's external-orchestrator seam: an unowned registration
        # goes to every extensible run rather than to nobody.
        self.assertEqual(pending_a, [knot])
        self.assertEqual(pending_b, [knot])

    def test_legacy_bare_knot_id_payload_still_broadcasts(self) -> None:
        """A publisher from before PIR-815 sends the bare knot id.

        It carries no attribution, so it is indistinguishable from an
        unowned registration and is delivered on the same terms.
        """
        pending_a: list[Any] = []
        pending_b: list[Any] = []
        self.store._subscribers[0] = _RunScopedSubscriber("run-a", pending_a)
        self.store._subscribers[1] = _RunScopedSubscriber("run-b", pending_b)

        knot = _make_knot("k1")
        self.store._live["k1"] = knot
        self.store._on_notify(None, 1234, "pirn_knots", "k1")

        self.assertEqual(pending_a, [knot])
        self.assertEqual(pending_b, [knot])


class TestPostgresStoreInheritance(unittest.TestCase):
    def test_is_tapestry_store(self) -> None:
        self.assertIsInstance(_make_store(), TapestryStore)

    def test_is_subscribable_store(self) -> None:
        self.assertIsInstance(_make_store(), SubscribableStore)
