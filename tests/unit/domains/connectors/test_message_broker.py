"""Tests for :class:`MessageBroker`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.message_broker import MessageBroker


async def _aiter():
    return
    yield  # pragma: no cover


class TestMessageBrokerInterface(unittest.IsolatedAsyncioTestCase):
    async def test_publish_raises_not_implemented(self) -> None:
        broker = MessageBroker()
        with self.assertRaises(NotImplementedError):
            await broker.publish("topic", b"data")

    async def test_consume_raises_not_implemented(self) -> None:
        broker = MessageBroker()
        with self.assertRaises(NotImplementedError):
            await broker.consume("topic")

    def test_clear_credentials_nulls_config(self) -> None:
        broker = MessageBroker()
        broker._config = object()
        broker._clear_credentials()
        self.assertIsNone(broker._config)
