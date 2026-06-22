"""Tests for :class:`KafkaBroker`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.connectors.streaming.kafka_broker import KafkaBroker
from pirn.connectors.streaming.kafka_config import KafkaConfig


def _make_config() -> KafkaConfig:
    return KafkaConfig(bootstrap_servers="localhost:9092")


def _make_producer() -> MagicMock:
    producer = MagicMock()
    producer.send_and_wait = AsyncMock(return_value=None)
    producer.stop = AsyncMock(return_value=None)
    return producer


class TestKafkaBrokerConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        broker = KafkaBroker(config=_make_config())
        self.assertIsInstance(broker, KafkaBroker)

    def test_config_property(self) -> None:
        cfg = _make_config()
        broker = KafkaBroker(config=cfg)
        self.assertIs(broker.config, cfg)


class TestKafkaBrokerPublish(unittest.IsolatedAsyncioTestCase):
    async def test_publish_sends_bytes(self) -> None:
        producer = _make_producer()
        broker = KafkaBroker(config=_make_config(), producer=producer)
        await broker.publish("my-topic", b"hello")
        producer.send_and_wait.assert_called_once()
        call_kwargs = producer.send_and_wait.call_args
        self.assertEqual(call_kwargs.args[0], "my-topic")

    async def test_publish_rejects_non_bytes_value(self) -> None:
        producer = _make_producer()
        broker = KafkaBroker(config=_make_config(), producer=producer)
        with self.assertRaises(TypeError):
            await broker.publish("topic", "not-bytes")  # type: ignore[arg-type]

    async def test_publish_rejects_non_bytes_key(self) -> None:
        producer = _make_producer()
        broker = KafkaBroker(config=_make_config(), producer=producer)
        with self.assertRaises(TypeError):
            await broker.publish("topic", b"val", key="not-bytes")  # type: ignore[arg-type]


class TestKafkaBrokerClose(unittest.IsolatedAsyncioTestCase):
    async def test_close_stops_producer(self) -> None:
        producer = _make_producer()
        broker = KafkaBroker(config=_make_config(), producer=producer)
        await broker.close()
        producer.stop.assert_called_once()
        self.assertIsNone(broker._producer)
