"""Unit tests for :class:`RabbitMQBroker` using stub aio_pika connection."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.rabbitmq_broker import RabbitMQBroker
from pirn.domains.connectors.streaming.rabbitmq_config import RabbitMQConfig


# ──────────────────────────────────────────────────────────── stub layer


class StubMessageContext:
    async def __aenter__(self) -> "StubMessageContext":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None


class StubMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def process(self) -> StubMessageContext:
        return StubMessageContext()


class StubQueueIterator:
    def __init__(self, messages: list[StubMessage]) -> None:
        self._messages = list(messages)

    async def __aenter__(self) -> "StubQueueIterator":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    def __aiter__(self) -> "StubQueueIterator":
        return self

    async def __anext__(self) -> StubMessage:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


class StubQueue:
    def __init__(self, name: str, messages: list[StubMessage]) -> None:
        self.name = name
        self._messages = messages

    def iterator(self) -> StubQueueIterator:
        return StubQueueIterator(self._messages)


class StubExchange:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(self, message: Any, *, routing_key: str) -> None:
        self.published.append(
            {
                "routing_key": routing_key,
                "body": getattr(message, "body", None),
                "correlation_id": getattr(message, "correlation_id", None),
                "headers": getattr(message, "headers", None),
            }
        )


class StubChannel:
    def __init__(self, queue_messages: dict[str, list[StubMessage]] | None = None) -> None:
        self.default_exchange = StubExchange()
        self._queues = queue_messages or {}
        self.declared_queues: list[str] = []
        self.closed = False

    async def declare_queue(self, name: str, *, durable: bool = True) -> StubQueue:
        self.declared_queues.append(name)
        return StubQueue(name, self._queues.get(name, []))

    async def close(self) -> None:
        self.closed = True


class StubConnection:
    def __init__(self, channel: StubChannel | None = None) -> None:
        self._channel = channel or StubChannel()
        self.closed = False

    async def channel(self) -> StubChannel:
        return self._channel

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_message_broker(self) -> None:
        broker = RabbitMQBroker(RabbitMQConfig(), connection=StubConnection())
        assert isinstance(broker, MessageBroker)
    
    
    def test_rejects_non_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be RabbitMQConfig"):
            RabbitMQBroker("nope", connection=StubConnection())  # type: ignore[arg-type]
    
    
# ─────────────────────────────────────────────────────────────── publish


class TestPublish(unittest.IsolatedAsyncioTestCase):
    async def test_publish_bytes_to_default_exchange(self) -> None:
        channel = StubChannel()
        broker = RabbitMQBroker(
            RabbitMQConfig(), connection=StubConnection(channel=channel)
        )
        await broker.publish("events", b"hello")
        assert channel.default_exchange.published == [
            {
                "routing_key": "events",
                "body": b"hello",
                "correlation_id": None,
                "headers": None,
            }
        ]

    async def test_publish_with_key_and_headers(self) -> None:
        channel = StubChannel()
        broker = RabbitMQBroker(
            RabbitMQConfig(), connection=StubConnection(channel=channel)
        )
        await broker.publish(
            "events", b"v", key=b"user-1", headers={"trace": b"abc"}
        )
        published = channel.default_exchange.published[0]
        assert published["body"] == b"v"
        assert published["correlation_id"] == "user-1"
        assert published["headers"] == {"trace": b"abc"}

    async def test_rejects_non_bytes_value(self) -> None:
        broker = RabbitMQBroker(RabbitMQConfig(), connection=StubConnection())
        with self.assertRaisesRegex(TypeError, "value must be bytes"):
            await broker.publish("t", "string")  # type: ignore[arg-type]

    async def test_rejects_non_bytes_key(self) -> None:
        broker = RabbitMQBroker(RabbitMQConfig(), connection=StubConnection())
        with self.assertRaisesRegex(TypeError, "key must be bytes"):
            await broker.publish("t", b"v", key="not-bytes")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────── consume


class TestConsume(unittest.IsolatedAsyncioTestCase):
    async def test_yields_messages_from_queue(self) -> None:
        messages = [StubMessage(b"a"), StubMessage(b"b")]
        channel = StubChannel(queue_messages={"events": messages})
        broker = RabbitMQBroker(
            RabbitMQConfig(), connection=StubConnection(channel=channel)
        )
        out: list[bytes] = []
        async for msg in await broker.consume("events"):
            out.append(msg.body)
        assert out == [b"a", b"b"]
        assert channel.declared_queues == ["events"]


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_is_idempotent(self) -> None:
        channel = StubChannel()
        connection = StubConnection(channel=channel)
        broker = RabbitMQBroker(RabbitMQConfig(), connection=connection)
        await broker.publish("t", b"v")
        await broker.close()
        await broker.close()
        assert connection.closed is True
        assert channel.closed is True

    async def test_publish_after_close_raises(self) -> None:
        broker = RabbitMQBroker(RabbitMQConfig(), connection=StubConnection())
        await broker.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await broker.publish("t", b"v")


# ─────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = RabbitMQConfig(user="alice", password="rmq-pw")
        text = repr(cfg)
        assert "rmq-pw" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = RabbitMQConfig(password="leaks")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
