"""Unit tests for :class:`PubSubBroker` using stub publisher/subscriber."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.pubsub_broker import PubSubBroker
from pirn.domains.connectors.streaming.pubsub_config import PubSubConfig


# ─────────────────────────────────────────────────────────── stub future


class StubFuture:
    def __init__(self, message_id: str = "mid-1") -> None:
        self._message_id = message_id

    def result(self, timeout: float | None = None) -> str:
        return self._message_id


# ──────────────────────────────────────────────────────── stub publisher


class StubPublisher:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.closed = False

    def topic_path(self, project: str, topic: str) -> str:
        return f"projects/{project}/topics/{topic}"

    def publish(self, topic_path: str, data: bytes, **attributes: str) -> StubFuture:
        self.published.append(
            {"topic_path": topic_path, "data": data, "attributes": attributes}
        )
        return StubFuture()

    def close(self) -> None:
        self.closed = True


# ─────────────────────────────────────────────────────── stub subscriber


class StubReceivedMessage:
    def __init__(self, ack_id: str, data: bytes) -> None:
        self.ack_id = ack_id
        self.message = type("M", (), {"data": data})()


class StubPullResponse:
    def __init__(self, received_messages: list[StubReceivedMessage]) -> None:
        self.received_messages = received_messages


class StubSubscriber:
    def __init__(self, batches: list[list[StubReceivedMessage]]) -> None:
        self._batches = list(batches)
        self.acked: list[list[str]] = []
        self.closed = False

    def subscription_path(self, project: str, subscription: str) -> str:
        return f"projects/{project}/subscriptions/{subscription}"

    def pull(self, request: dict[str, Any]) -> StubPullResponse:
        if not self._batches:
            return StubPullResponse([])
        return StubPullResponse(self._batches.pop(0))

    def acknowledge(self, request: dict[str, Any]) -> None:
        self.acked.append(list(request["ack_ids"]))

    def close(self) -> None:
        self.closed = True


# ─────────────────────────────────────────────────────── conformance


def test_implements_message_broker() -> None:
    broker = PubSubBroker(
        PubSubConfig(project="p"), publisher=StubPublisher(), subscriber=StubSubscriber([])
    )
    assert isinstance(broker, MessageBroker)


def test_rejects_non_config() -> None:
    with pytest.raises(TypeError, match="must be PubSubConfig"):
        PubSubBroker("nope", publisher=StubPublisher())  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────── publish


@pytest.mark.asyncio
class TestPublish:
    async def test_publish_bytes_to_topic_path(self) -> None:
        pub = StubPublisher()
        broker = PubSubBroker(PubSubConfig(project="my-project"), publisher=pub)
        await broker.publish("events", b"hello")
        assert pub.published == [
            {
                "topic_path": "projects/my-project/topics/events",
                "data": b"hello",
                "attributes": {},
            }
        ]

    async def test_publish_with_key_and_headers(self) -> None:
        pub = StubPublisher()
        broker = PubSubBroker(PubSubConfig(project="p"), publisher=pub)
        await broker.publish(
            "events", b"v", key=b"user-1", headers={"trace": b"abc"}
        )
        published = pub.published[0]
        assert published["attributes"]["pirn-key"] == "user-1"
        assert published["attributes"]["trace"] == "abc"

    async def test_rejects_non_bytes_value(self) -> None:
        broker = PubSubBroker(PubSubConfig(project="p"), publisher=StubPublisher())
        with pytest.raises(TypeError, match="value must be bytes"):
            await broker.publish("t", "string")  # type: ignore[arg-type]

    async def test_rejects_non_bytes_key(self) -> None:
        broker = PubSubBroker(PubSubConfig(project="p"), publisher=StubPublisher())
        with pytest.raises(TypeError, match="key must be bytes"):
            await broker.publish("t", b"v", key="not-bytes")  # type: ignore[arg-type]

    async def test_publish_requires_project_for_short_topic(self) -> None:
        broker = PubSubBroker(PubSubConfig(), publisher=StubPublisher())
        with pytest.raises(ValueError, match="project must be set"):
            await broker.publish("events", b"v")


# ──────────────────────────────────────────────────────────── consume


@pytest.mark.asyncio
class TestConsume:
    async def test_yields_subscriber_messages(self) -> None:
        sub = StubSubscriber(
            batches=[
                [
                    StubReceivedMessage("a1", b"alpha"),
                    StubReceivedMessage("a2", b"beta"),
                ]
            ]
        )
        broker = PubSubBroker(
            PubSubConfig(project="p"), publisher=StubPublisher(), subscriber=sub
        )
        out: list[bytes] = []
        async for rec in await broker.consume("my-sub"):
            out.append(rec.message.data)
        assert out == [b"alpha", b"beta"]
        assert sub.acked == [["a1", "a2"]]


# ──────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_is_idempotent(self) -> None:
        pub = StubPublisher()
        sub = StubSubscriber([])
        broker = PubSubBroker(PubSubConfig(project="p"), publisher=pub, subscriber=sub)
        await broker.close()
        await broker.close()
        assert pub.closed is True
        assert sub.closed is True

    async def test_publish_after_close_raises(self) -> None:
        broker = PubSubBroker(PubSubConfig(project="p"), publisher=StubPublisher())
        await broker.close()
        with pytest.raises(RuntimeError, match="closed"):
            await broker.publish("t", b"v")


# ─────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_service_account_json(self) -> None:
        cfg = PubSubConfig(project="p", service_account_json="/etc/secret.json")
        text = repr(cfg)
        assert "/etc/secret.json" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_service_account_json(self) -> None:
        cfg = PubSubConfig(project="p", service_account_json="leaks")
        d = cfg.to_audit_dict()
        assert d["service_account_json"] == "<redacted>"
