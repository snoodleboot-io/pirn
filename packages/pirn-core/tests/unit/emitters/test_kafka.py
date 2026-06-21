"""Unit tests for KafkaEmitter."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.emitters.kafka import KafkaEmitter


def _make_status_event() -> MagicMock:
    e = MagicMock()
    e.run_id = "r1"
    e.model_dump_json = MagicMock(return_value='{"run_id":"r1"}')
    return e


def _make_lineage() -> MagicMock:
    r = MagicMock()
    r.run_id = "r1"
    r.model_dump_json = MagicMock(return_value='{"run_id":"r1"}')
    return r


def _make_run_result() -> MagicMock:
    rr = MagicMock()
    rr.run_id = "r1"
    rr.model_dump_json = MagicMock(return_value='{"run_id":"r1"}')
    return rr


class TestKafkaEmitterConstruction(unittest.TestCase):
    def test_requires_producer_or_topic(self) -> None:
        with self.assertRaisesRegex(TypeError, "producer"):
            KafkaEmitter()

    def test_accepts_producer(self) -> None:
        producer = MagicMock()
        emitter = KafkaEmitter(producer=producer, topic="t")
        self.assertIsNotNone(emitter)

    def test_accepts_topic(self) -> None:
        emitter = KafkaEmitter(topic="pirn-events")
        self.assertIsNotNone(emitter)

    def test_per_type_topics_default_to_default(self) -> None:
        emitter = KafkaEmitter(topic="default-topic")
        self.assertEqual(emitter._topic_status, "default-topic")
        self.assertEqual(emitter._topic_lineage, "default-topic")
        self.assertEqual(emitter._topic_result, "default-topic")

    def test_per_type_topics_can_be_overridden(self) -> None:
        emitter = KafkaEmitter(
            topic="default",
            topic_status="status-topic",
            topic_lineage="lineage-topic",
            topic_result="result-topic",
        )
        self.assertEqual(emitter._topic_status, "status-topic")
        self.assertEqual(emitter._topic_lineage, "lineage-topic")
        self.assertEqual(emitter._topic_result, "result-topic")


class TestKafkaEmitterEvents(unittest.IsolatedAsyncioTestCase):
    def _make_emitter_with_mock_producer(self) -> tuple[KafkaEmitter, MagicMock]:
        producer = MagicMock()
        producer.send_and_wait = AsyncMock()
        emitter = KafkaEmitter(producer=producer, topic="pirn-events")
        return emitter, producer

    async def test_on_status_publishes(self) -> None:
        emitter, producer = self._make_emitter_with_mock_producer()
        await emitter.on_status(_make_status_event())
        producer.send_and_wait.assert_called_once()

    async def test_on_lineage_publishes(self) -> None:
        emitter, producer = self._make_emitter_with_mock_producer()
        await emitter.on_lineage(_make_lineage())
        producer.send_and_wait.assert_called_once()

    async def test_on_run_result_publishes(self) -> None:
        emitter, producer = self._make_emitter_with_mock_producer()
        await emitter.on_run_result(_make_run_result())
        producer.send_and_wait.assert_called_once()

    async def test_on_status_skipped_when_no_topic(self) -> None:
        producer = MagicMock()
        producer.send_and_wait = AsyncMock()
        emitter = KafkaEmitter(producer=producer, topic=None, topic_lineage="lineage")
        await emitter.on_status(_make_status_event())
        producer.send_and_wait.assert_not_called()

    async def test_close_stops_producer(self) -> None:
        producer = MagicMock()
        producer.stop = AsyncMock()
        emitter = KafkaEmitter(producer=producer, topic="t")
        await emitter.close()
        producer.stop.assert_called_once()

    async def test_close_with_no_producer_is_noop(self) -> None:
        emitter = KafkaEmitter(topic="t")
        await emitter.close()  # no exception
