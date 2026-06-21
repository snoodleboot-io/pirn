"""Unit tests for :class:`AzureServiceBusBroker` using stub Service Bus client."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.message_broker import MessageBroker
from pirn.connectors.streaming.azure_servicebus_broker import (
    AzureServiceBusBroker,
)
from pirn.connectors.streaming.azure_servicebus_config import (
    AzureServiceBusConfig,
)

# ──────────────────────────────────────────────────────────── stub layer


class StubSender:
    def __init__(self) -> None:
        self.sent: list[Any] = []
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> StubSender:
        self.entered = True
        return self

    async def __aexit__(self, *_args: Any) -> None:
        self.exited = True

    async def send_messages(self, message: Any) -> None:
        self.sent.append(message)


class StubReceiver:
    def __init__(self, messages: list[Any]) -> None:
        self._messages = list(messages)
        self.completed: list[Any] = []
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> StubReceiver:
        self.entered = True
        return self

    async def __aexit__(self, *_args: Any) -> None:
        self.exited = True

    def __aiter__(self) -> StubReceiver:
        return self

    async def __anext__(self) -> Any:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def complete_message(self, message: Any) -> None:
        self.completed.append(message)


class StubServiceBusClient:
    def __init__(self, *, receiver_messages: dict[str, list[Any]] | None = None,) -> None:
        self.senders: dict[str, StubSender] = {}
        self.receivers: dict[str, StubReceiver] = {}
        self._receiver_messages = receiver_messages or {}
        self.closed = False

    def get_queue_sender(self, queue_name: str) -> StubSender:
        sender = self.senders.setdefault(queue_name, StubSender())
        return sender

    def get_queue_receiver(self, queue_name: str) -> StubReceiver:
        receiver = StubReceiver(self._receiver_messages.get(queue_name, []))
        self.receivers[queue_name] = receiver
        return receiver

    async def close(self) -> None:
        self.closed = True


class StubMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body


# ───────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_message_broker(self) -> None:
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=StubServiceBusClient(),
        )
        assert isinstance(broker, MessageBroker)
    
    
    def test_rejects_non_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be AzureServiceBusConfig"):
            AzureServiceBusBroker("nope", client=StubServiceBusClient())  # type: ignore[arg-type]
    
    
    def test_requires_connection_or_injected_client(self) -> None:
        with self.assertRaisesRegex(ValueError, "connection_string"):
            AzureServiceBusBroker(AzureServiceBusConfig())
    
    
# ─────────────────────────────────────────────────────────────── publish


class TestPublish(unittest.IsolatedAsyncioTestCase):
    async def test_publish_bytes_uses_queue_sender(self) -> None:
        client = StubServiceBusClient()
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=client,
        )
        await broker.publish("events", b"hello")
        sender = client.senders["events"]
        assert len(sender.sent) == 1
        sent_message = sender.sent[0]
        body = getattr(sent_message, "body", None)
        # Real ServiceBusMessage.body is a generator; consume it.
        if hasattr(body, "__iter__") and not isinstance(body, (bytes, bytearray)):
            body = b"".join(body)
        assert body == b"hello"
        assert sender.entered and sender.exited

    async def test_publish_with_key_and_headers(self) -> None:
        client = StubServiceBusClient()
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=client,
        )
        await broker.publish(
            "events", b"v", key=b"user-1", headers={"trace": b"abc"}
        )
        sender = client.senders["events"]
        sent = sender.sent[0]
        body = sent.body
        if hasattr(body, "__iter__") and not isinstance(body, (bytes, bytearray)):
            body = b"".join(body)
        assert body == b"v"
        assert sent.session_id == "user-1"
        assert sent.application_properties == {"trace": b"abc"}

    async def test_rejects_non_bytes_value(self) -> None:
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=StubServiceBusClient(),
        )
        with self.assertRaisesRegex(TypeError, "value must be bytes"):
            await broker.publish("t", "string")  # type: ignore[arg-type]

    async def test_rejects_non_bytes_key(self) -> None:
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=StubServiceBusClient(),
        )
        with self.assertRaisesRegex(TypeError, "key must be bytes"):
            await broker.publish("t", b"v", key="not-bytes")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────── consume


class TestConsume(unittest.IsolatedAsyncioTestCase):
    async def test_yields_messages_from_queue(self) -> None:
        messages = [StubMessage(b"a"), StubMessage(b"b")]
        client = StubServiceBusClient(receiver_messages={"events": messages})
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=client,
        )
        out: list[bytes] = []
        async for msg in await broker.consume("events"):
            out.append(msg.body)
        assert out == [b"a", b"b"]
        receiver = client.receivers["events"]
        assert receiver.entered and receiver.exited
        assert len(receiver.completed) == 2


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_is_idempotent(self) -> None:
        client = StubServiceBusClient()
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=client,
        )
        await broker.publish("t", b"v")
        await broker.close()
        await broker.close()
        assert client.closed is True

    async def test_publish_after_close_raises(self) -> None:
        broker = AzureServiceBusBroker(
            AzureServiceBusConfig(connection_string="Endpoint=sb://x"),
            client=StubServiceBusClient(),
        )
        await broker.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await broker.publish("t", b"v")


# ─────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_connection_string(self) -> None:
        cfg = AzureServiceBusConfig(
            connection_string="Endpoint=sb://leak;SharedAccessKey=secret"
        )
        text = repr(cfg)
        assert "secret" not in text
        assert "Endpoint=sb://leak" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_connection_string(self) -> None:
        cfg = AzureServiceBusConfig(connection_string="leaks")
        d = cfg.to_audit_dict()
        assert d["connection_string"] == "<redacted>"
