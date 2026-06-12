"""Unit tests for :class:`KafkaBroker` using stub producer / consumer."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.message_broker import MessageBroker
from pirn.connectors.streaming.kafka_broker import KafkaBroker
from pirn.connectors.streaming.kafka_config import KafkaConfig

# ───────────────────────────────────────────────────────── stub producer


class StubProducer:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send_and_wait(
        self, topic: str, *, value: bytes,
        key: bytes | None = None, headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
        self.published.append(
            {"topic": topic, "value": value, "key": key, "headers": headers}
        )


class StubConsumer:
    def __init__(self, records: list[Any]) -> None:
        self.records = records
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def __aiter__(self):  # type: ignore[no-untyped-def]
        return self._iter()

    async def _iter(self):
        for r in self.records:
            yield r


def _record(topic: str, value: bytes, *, key: bytes | None = None) -> Any:
    return type(
        "Rec",
        (),
        {"topic": topic, "value": value, "key": key, "headers": []},
    )()


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_message_broker(self) -> None:
        broker = KafkaBroker(KafkaConfig(), producer=StubProducer())
        assert isinstance(broker, MessageBroker)
    
    
# ─────────────────────────────────────────────────────────────── publish


class TestPublish(unittest.IsolatedAsyncioTestCase):
    async def test_publish_bytes_value(self) -> None:
        prod = StubProducer()
        broker = KafkaBroker(KafkaConfig(), producer=prod)
        await broker.publish("events", b"hello")
        assert prod.published == [
            {"topic": "events", "value": b"hello", "key": None, "headers": None}
        ]

    async def test_publish_with_key_and_headers(self) -> None:
        prod = StubProducer()
        broker = KafkaBroker(KafkaConfig(), producer=prod)
        await broker.publish(
            "events", b"v", key=b"k", headers={"trace-id": b"abc"}
        )
        published = prod.published[0]
        assert published["key"] == b"k"
        assert published["headers"] == [("trace-id", b"abc")]

    async def test_rejects_non_bytes_value(self) -> None:
        broker = KafkaBroker(KafkaConfig(), producer=StubProducer())
        with self.assertRaisesRegex(TypeError, "value must be bytes"):
            await broker.publish("t", "string")  # type: ignore[arg-type]

    async def test_rejects_non_bytes_key(self) -> None:
        broker = KafkaBroker(KafkaConfig(), producer=StubProducer())
        with self.assertRaisesRegex(TypeError, "key must be bytes"):
            await broker.publish("t", b"v", key="not-bytes")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────── consume


class TestConsume(unittest.IsolatedAsyncioTestCase):
    async def test_yields_records_for_topic(self) -> None:
        records = [_record("events", b"a"), _record("events", b"b")]
        consumer = StubConsumer(records)

        def factory(topic: str, group: str | None) -> Any:
            assert topic == "events"
            return consumer

        broker = KafkaBroker(
            KafkaConfig(group_id="g1"),
            producer=StubProducer(),
            consumer_factory=factory,
        )
        out: list[bytes] = []
        async for rec in await broker.consume("events"):
            out.append(rec.value)
        assert out == [b"a", b"b"]
        assert consumer.started and consumer.stopped

    async def test_passes_explicit_group_id(self) -> None:
        captured: dict[str, str | None] = {}

        def factory(topic: str, group: str | None) -> Any:
            captured["group"] = group
            return StubConsumer([])

        broker = KafkaBroker(
            KafkaConfig(group_id="default-g"),
            producer=StubProducer(),
            consumer_factory=factory,
        )
        async for _ in await broker.consume("t", group="explicit-g"):
            pass
        assert captured["group"] == "explicit-g"

    async def test_falls_back_to_config_group_id(self) -> None:
        captured: dict[str, str | None] = {}

        def factory(topic: str, group: str | None) -> Any:
            captured["group"] = group
            return StubConsumer([])

        broker = KafkaBroker(
            KafkaConfig(group_id="default-g"),
            producer=StubProducer(),
            consumer_factory=factory,
        )
        async for _ in await broker.consume("t"):
            pass
        assert captured["group"] == "default-g"


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_stops_producer(self) -> None:
        prod = StubProducer()
        broker = KafkaBroker(KafkaConfig(), producer=prod)
        await broker.publish("t", b"v")
        await broker.close()
        assert prod.stopped is True

    async def test_publish_after_close_raises(self) -> None:
        broker = KafkaBroker(KafkaConfig(), producer=StubProducer())
        await broker.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await broker.publish("t", b"v")


# ───────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_sasl_password(self) -> None:
        cfg = KafkaConfig(
            bootstrap_servers="kafka:9092",
            sasl_username="alice",
            sasl_password="my-kafka-pw",
            sasl_mechanism="SCRAM-SHA-256",
        )
        text = repr(cfg)
        assert "my-kafka-pw" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = KafkaConfig(sasl_password="leaks")
        d = cfg.to_audit_dict()
        assert d["sasl_password"] == "<redacted>"
