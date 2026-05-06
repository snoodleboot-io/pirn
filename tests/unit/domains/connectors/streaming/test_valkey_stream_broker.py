"""Tests for :class:`ValkeyStreamBroker`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.domains.connectors.streaming.valkey_stream_broker import ValkeyStreamBroker
from pirn.domains.connectors.streaming.valkey_stream_config import ValkeyStreamConfig


def _make_config(**kwargs) -> ValkeyStreamConfig:
    return ValkeyStreamConfig(consumer_group="grp", **kwargs)


def _make_client() -> MagicMock:
    client = MagicMock()
    client.xadd = AsyncMock(return_value=None)
    client.close = MagicMock(return_value=None)
    return client


class TestValkeyStreamBrokerConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        broker = ValkeyStreamBroker(config=_make_config())
        self.assertIsInstance(broker, ValkeyStreamBroker)

    def test_config_property(self) -> None:
        cfg = _make_config()
        broker = ValkeyStreamBroker(config=cfg)
        self.assertIs(broker.config, cfg)


class TestValkeyStreamBrokerPublish(unittest.IsolatedAsyncioTestCase):
    async def test_publish_calls_xadd(self) -> None:
        client = _make_client()
        broker = ValkeyStreamBroker(config=_make_config(), client=client)
        await broker.publish("my-stream", b"data")
        client.xadd.assert_called_once()
        call_args = client.xadd.call_args
        self.assertEqual(call_args.args[0], "my-stream")
        fields = call_args.args[1]
        self.assertEqual(fields[b"v"], b"data")

    async def test_publish_rejects_non_bytes(self) -> None:
        client = _make_client()
        broker = ValkeyStreamBroker(config=_make_config(), client=client)
        with self.assertRaises(TypeError):
            await broker.publish("stream", "not-bytes")  # type: ignore[arg-type]

    async def test_publish_includes_key_field(self) -> None:
        client = _make_client()
        broker = ValkeyStreamBroker(config=_make_config(), client=client)
        await broker.publish("stream", b"val", key=b"k1")
        fields = client.xadd.call_args.args[1]
        self.assertEqual(fields[b"k"], b"k1")

    async def test_publish_includes_header_fields(self) -> None:
        client = _make_client()
        broker = ValkeyStreamBroker(config=_make_config(), client=client)
        await broker.publish("stream", b"val", headers={"trace": b"abc"})
        fields = client.xadd.call_args.args[1]
        self.assertEqual(fields[b"h:trace"], b"abc")


class TestValkeyStreamBrokerClose(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_client_close(self) -> None:
        client = _make_client()
        broker = ValkeyStreamBroker(config=_make_config(), client=client)
        await broker.close()
        client.close.assert_called_once()
        self.assertIsNone(broker._client)
