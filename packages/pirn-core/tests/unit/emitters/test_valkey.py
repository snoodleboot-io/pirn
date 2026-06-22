"""Unit tests for ValKeyEmitter."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.emitters.valkey import ValKeyEmitter


def _make_client() -> MagicMock:
    client = MagicMock()
    client.publish = AsyncMock()
    client.close = AsyncMock()
    return client


def _make_event() -> MagicMock:
    e = MagicMock()
    e.model_dump_json = MagicMock(return_value='{}')
    return e


class TestValKeyEmitterConstruction(unittest.TestCase):
    def test_requires_client_or_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "client"):
            ValKeyEmitter()

    def test_accepts_client(self) -> None:
        emitter = ValKeyEmitter(client=_make_client())
        self.assertIsNotNone(emitter)

    def test_accepts_config(self) -> None:
        emitter = ValKeyEmitter(config=MagicMock())
        self.assertIsNotNone(emitter)

    def test_default_channels(self) -> None:
        emitter = ValKeyEmitter(client=_make_client())
        self.assertEqual(emitter._channel_status, "pirn:status")
        self.assertEqual(emitter._channel_lineage, "pirn:lineage")
        self.assertEqual(emitter._channel_result, "pirn:result")

    def test_custom_channels(self) -> None:
        emitter = ValKeyEmitter(
            client=_make_client(),
            channel_status="s",
            channel_lineage="l",
            channel_result="r",
        )
        self.assertEqual(emitter._channel_status, "s")


class TestValKeyEmitterEvents(unittest.IsolatedAsyncioTestCase):
    async def test_on_status_publishes(self) -> None:
        client = _make_client()
        emitter = ValKeyEmitter(client=client)
        await emitter.on_status(_make_event())
        client.publish.assert_called_once_with("pirn:status", "{}")

    async def test_on_lineage_publishes(self) -> None:
        client = _make_client()
        emitter = ValKeyEmitter(client=client)
        await emitter.on_lineage(_make_event())
        client.publish.assert_called_once_with("pirn:lineage", "{}")

    async def test_on_run_result_publishes(self) -> None:
        client = _make_client()
        emitter = ValKeyEmitter(client=client)
        await emitter.on_run_result(_make_event())
        client.publish.assert_called_once_with("pirn:result", "{}")

    async def test_close_closes_client(self) -> None:
        client = _make_client()
        emitter = ValKeyEmitter(client=client)
        await emitter.close()
        client.close.assert_called_once()

    async def test_close_with_no_client_is_noop(self) -> None:
        emitter = ValKeyEmitter(config=MagicMock())
        await emitter.close()  # no exception
