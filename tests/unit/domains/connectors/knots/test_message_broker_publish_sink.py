"""Tests for :class:`MessageBrokerPublishSink` using a stub broker."""

from __future__ import annotations

from typing import Any, AsyncIterator
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.knots.message_broker_publish_sink import (
    MessageBrokerPublishSink,
)
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.tapestry import Tapestry


class StubBroker(MessageBroker):
    """In-memory broker for testing the Sink contract."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(self, topic: str, value: bytes, *, key: bytes | None = None, headers: dict[str, bytes] | None = None,) -> None:
        self.published.append(
            {"topic": topic, "value": value, "key": key, "headers": headers}
        )

    async def consume(self, topic: str, *, group: str | None = None) -> AsyncIterator[Any]:
        async def _empty() -> AsyncIterator[Any]:
            if False:
                yield None

        return _empty()


@knot
async def emit_message() -> bytes:
    return b"hello-broker"



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_parents_bytes_to_topic(self) -> None:
        broker = StubBroker()
    
        with Tapestry() as t:
            message = emit_message(_config=KnotConfig(id="msg"))
            MessageBrokerPublishSink(
                broker=broker,
                topic="events",
                value=message,
                _config=KnotConfig(id="publish"),
            )
    
        result = await t.run(RunRequest())
        assert result.succeeded
        assert broker.published == [
            {"topic": "events", "value": b"hello-broker", "key": None, "headers": None}
        ]
    
    
    async def test_publishes_with_key_and_headers(self) -> None:
        broker = StubBroker()
    
        with Tapestry() as t:
            message = emit_message(_config=KnotConfig(id="msg"))
            MessageBrokerPublishSink(
                broker=broker,
                topic="events",
                value=message,
                key=b"user-1",
                headers={"trace-id": b"abc"},
                _config=KnotConfig(id="publish"),
            )
    
        await t.run(RunRequest())
        published = broker.published[0]
        assert published["key"] == b"user-1"
        assert published["headers"] == {"trace-id": b"abc"}
    
    
    def test_construct_rejects_non_broker(self) -> None:
        @knot
        async def emit() -> bytes:
            return b""
    
        with Tapestry():
            msg = emit(_config=KnotConfig(id="emit"))
            with self.assertRaisesRegex(TypeError, "MessageBroker"):
                MessageBrokerPublishSink(
                    broker=object(),  # type: ignore[arg-type]
                    topic="t",
                    value=msg,
                    _config=KnotConfig(id="publish"),
                )
