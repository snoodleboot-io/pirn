"""Tests for :class:`MessageBrokerKnot` calling process() directly."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.knots.message_broker_knot import MessageBrokerKnot
from pirn.domains.connectors.message_broker import MessageBroker


class StubBroker(MessageBroker):
    async def publish(
        self, topic: str, value: bytes, *,
        key: bytes | None = None, headers: dict[str, bytes] | None = None,
    ) -> None:
        pass

    async def consume(self, topic: str, *, group: str | None = None) -> AsyncIterator[Any]:
        async def _empty() -> AsyncIterator[Any]:
            if False:
                yield None
        return _empty()


class TestMessageBrokerKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_broker_unchanged(self) -> None:
        broker = StubBroker()
        knot = MessageBrokerKnot(broker=broker, _config=KnotConfig(id="broker"))
        result = await knot.process(broker=broker)
        assert result is broker

    async def test_accepts_scalar_broker_at_build_time(self) -> None:
        broker = StubBroker()
        knot = MessageBrokerKnot(broker=broker, _config=KnotConfig(id="broker"))
        result = await knot.process(broker=broker)
        assert isinstance(result, StubBroker)
