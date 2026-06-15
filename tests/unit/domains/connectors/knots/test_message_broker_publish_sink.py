"""Tests for :class:`MessageBrokerPublishSink` calling process() directly."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.knots.message_broker_knot import MessageBrokerKnot
from pirn.connectors.knots.message_broker_publish_sink import MessageBrokerPublishSink
from pirn.connectors.message_broker import MessageBroker
from pirn.core.knot_config import KnotConfig


class StubBroker(MessageBroker):
    """In-memory broker for testing the Sink contract."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(
        self, topic: str, value: bytes, *,
        key: bytes | None = None, headers: dict[str, bytes] | None = None,
    ) -> None:
        self.published.append(
            {"topic": topic, "value": value, "key": key, "headers": headers}
        )

    async def consume(self, topic: str, *, group: str | None = None) -> AsyncIterator[Any]:
        async def _empty() -> AsyncIterator[Any]:
            if False:
                yield None
        return _empty()


class TestMessageBrokerPublishSink(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.broker = StubBroker()
        broker_knot = MessageBrokerKnot(broker=self.broker, _config=KnotConfig(id="broker"))
        # Use broker_knot as a dummy for value wiring; process() called directly
        self.sink = MessageBrokerPublishSink(
            broker=broker_knot,
            topic="events",
            value=broker_knot,
            _config=KnotConfig(id="publish"),
        )

    async def test_publishes_bytes_to_topic(self) -> None:
        await self.sink.process(broker=self.broker, topic="events", value=b"hello-broker")
        assert self.broker.published == [
            {"topic": "events", "value": b"hello-broker", "key": None, "headers": None}
        ]

    async def test_publishes_with_key_and_headers(self) -> None:
        await self.sink.process(
            broker=self.broker,
            topic="events",
            value=b"msg",
            key=b"user-1",
            headers={"trace-id": b"abc"},
        )
        published = self.broker.published[0]
        assert published["key"] == b"user-1"
        assert published["headers"] == {"trace-id": b"abc"}

    async def test_rejects_non_broker(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.sink.process(
                broker=object(),  # type: ignore[arg-type]
                topic="events",
                value=b"msg",
            )
        assert "MessageBroker" in str(ctx.exception)

    async def test_rejects_empty_topic(self) -> None:
        with self.assertRaises(ValueError):
            await self.sink.process(broker=self.broker, topic="", value=b"msg")

    async def test_rejects_non_bytes_value(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.sink.process(
                broker=self.broker,
                topic="events",
                value="not bytes",  # type: ignore[arg-type]
            )
        assert "bytes" in str(ctx.exception)


class TestMessageBrokerKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_broker_unchanged(self) -> None:
        broker = StubBroker()
        knot = MessageBrokerKnot(broker=broker, _config=KnotConfig(id="broker"))
        result = await knot.process(broker=broker)
        assert result is broker
