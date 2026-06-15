"""Tests for ValKeyStore (TapestryStore + SubscribableStore)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends.base.subscribable_store import SubscribableStore
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.valkey.valkey_store import ValKeyStore


def _make_knot(knot_id: str) -> MagicMock:
    knot = MagicMock()
    knot.knot_id = knot_id
    knot.config = MagicMock()
    knot.config.model_dump_json = MagicMock(return_value="{}")
    knot.parents = {}
    return knot


def _make_mock_client() -> AsyncMock:
    client = AsyncMock()
    client.hset = AsyncMock()
    client.sadd = AsyncMock()
    client.publish = AsyncMock()
    return client


class TestValKeyStoreConstruction(unittest.TestCase):
    def test_requires_client_or_config(self) -> None:
        with self.assertRaises(TypeError):
            ValKeyStore()

    def test_accepts_injected_client(self) -> None:
        client = AsyncMock()
        store = ValKeyStore(client=client)
        self.assertIsNotNone(store)


class TestValKeyStoreLiveOperations(unittest.TestCase):
    """get / all / snapshot use in-process live dict — no network calls."""

    def setUp(self) -> None:
        self.client = _make_mock_client()
        self.store = ValKeyStore(client=self.client)

    def test_get_returns_none_for_missing(self) -> None:
        self.assertIsNone(self.store.get("missing"))

    def test_all_empty_initially(self) -> None:
        self.assertEqual(self.store.all(), [])

    def test_snapshot_empty_initially(self) -> None:
        snap = self.store.snapshot()
        self.assertIsInstance(snap, TapestrySnapshot)
        self.assertEqual(snap.knot_ids, [])

    def test_register_same_id_different_instance_raises(self) -> None:
        k1 = _make_knot("k1")
        k2 = _make_knot("k1")
        # Inject into live dict directly to avoid needing running loop
        self.store._live["k1"] = k1
        with self.assertRaises(ValueError):
            self.store.register(k2)


class TestValKeyStoreAsyncRegister(unittest.IsolatedAsyncioTestCase):
    """aregister() pushes knot metadata to ValKey."""

    async def test_aregister_calls_hset_and_sadd(self) -> None:
        client = _make_mock_client()
        store = ValKeyStore(client=client)
        knot = _make_knot("k1")
        await store.aregister(knot)
        client.hset.assert_called_once()
        client.sadd.assert_called_once()

    async def test_aregister_idempotent_for_same_instance(self) -> None:
        client = _make_mock_client()
        store = ValKeyStore(client=client)
        knot = _make_knot("k1")
        await store.aregister(knot)
        await store.aregister(knot)  # must not raise
        # hset called twice (re-registration updates metadata)
        self.assertEqual(client.hset.call_count, 2)

    async def test_aregister_different_instance_raises(self) -> None:
        client = _make_mock_client()
        store = ValKeyStore(client=client)
        k1 = _make_knot("k1")
        k2 = _make_knot("k1")
        await store.aregister(k1)
        with self.assertRaises(ValueError):
            await store.aregister(k2)

    async def test_get_and_all_reflect_registered_knot(self) -> None:
        client = _make_mock_client()
        store = ValKeyStore(client=client)
        knot = _make_knot("k1")
        await store.aregister(knot)
        self.assertIs(store.get("k1"), knot)
        self.assertIn(knot, store.all())

    async def test_snapshot_reflects_live_dict(self) -> None:
        client = _make_mock_client()
        store = ValKeyStore(client=client)
        knot = _make_knot("k1")
        await store.aregister(knot)
        snap = store.snapshot()
        self.assertIn("k1", snap.knot_ids)


class TestValKeyStoreSubscription(unittest.IsolatedAsyncioTestCase):
    """subscribe / unsubscribe."""

    def setUp(self) -> None:
        self.client = _make_mock_client()
        self.store = ValKeyStore(client=self.client)

    async def test_subscribe_returns_token(self) -> None:
        token = self.store.subscribe(lambda k: None)
        self.assertIsNotNone(token)

    def test_unsubscribe_unknown_token_is_idempotent(self) -> None:
        self.store.unsubscribe(9999)

    async def test_unsubscribe_removes_callback(self) -> None:
        received: list = []
        token = self.store.subscribe(received.append)
        self.store.unsubscribe(token)
        self.assertNotIn(token, self.store._subscribers)


class TestValKeyStoreOnMessage(unittest.TestCase):
    """_on_message dispatches to subscribers when knot is in live dict."""

    def setUp(self) -> None:
        self.client = _make_mock_client()
        self.store = ValKeyStore(client=self.client)

    def test_on_message_calls_subscriber_for_known_knot(self) -> None:
        knot = _make_knot("k1")
        self.store._live["k1"] = knot
        received: list = []
        self.store._subscribers[0] = received.append

        msg = MagicMock()
        msg.message = b"k1"
        self.store._on_message(msg, None)
        self.assertEqual(received, [knot])

    def test_on_message_ignores_unknown_knot(self) -> None:
        received: list = []
        self.store._subscribers[0] = received.append

        msg = MagicMock()
        msg.message = b"unknown"
        self.store._on_message(msg, None)
        self.assertEqual(received, [])

    def test_on_message_subscriber_exception_does_not_propagate(self) -> None:
        knot = _make_knot("k1")
        self.store._live["k1"] = knot

        def _bad(k: Any) -> None:
            raise RuntimeError("boom")

        self.store._subscribers[0] = _bad

        msg = MagicMock()
        msg.message = b"k1"
        self.store._on_message(msg, None)  # must not raise


class TestValKeyStoreInheritance(unittest.TestCase):
    def test_is_tapestry_store(self) -> None:
        client = AsyncMock()
        self.assertIsInstance(ValKeyStore(client=client), TapestryStore)

    def test_is_subscribable_store(self) -> None:
        client = AsyncMock()
        self.assertIsInstance(ValKeyStore(client=client), SubscribableStore)
