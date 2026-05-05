"""Unit tests for KafkaStreamingSource."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.streaming.kafka import KafkaStreamingSource


def _mock_msg(value: bytes) -> MagicMock:
    msg = MagicMock()
    msg.value = value
    return msg


class TestKafkaStreamingSourceConstruction(unittest.TestCase):
    def test_requires_consumer_or_topic(self) -> None:
        with self.assertRaisesRegex(TypeError, "consumer"):
            KafkaStreamingSource(parameter_name="x")

    def test_accepts_consumer(self) -> None:
        consumer = MagicMock()
        src = KafkaStreamingSource(consumer=consumer, parameter_name="msg")
        self.assertIsNotNone(src)

    def test_accepts_topic(self) -> None:
        src = KafkaStreamingSource(topic="my-topic", parameter_name="msg")
        self.assertIsNotNone(src)

    def test_default_name(self) -> None:
        src = KafkaStreamingSource(topic="t", parameter_name="x")
        self.assertEqual(src.name, "KafkaStreamingSource")

    def test_custom_name(self) -> None:
        src = KafkaStreamingSource(topic="t", parameter_name="x", name="Mine")
        self.assertEqual(src.name, "Mine")


class TestKafkaStreamingSourceDefaultDecoder(unittest.TestCase):
    def test_decodes_json_bytes(self) -> None:
        msg = _mock_msg(b'{"key":"val"}')
        src = KafkaStreamingSource(topic="t", parameter_name="x")
        # Access private decoder via name mangling
        decoder = src._KafkaStreamingSource__default_decoder
        result = decoder(msg)
        self.assertEqual(result, {"key": "val"})

    def test_decodes_json_string(self) -> None:
        msg = MagicMock()
        msg.value = '{"n":42}'
        src = KafkaStreamingSource(topic="t", parameter_name="x")
        decoder = src._KafkaStreamingSource__default_decoder
        self.assertEqual(decoder(msg), {"n": 42})


class TestKafkaStreamingSourceClose(unittest.IsolatedAsyncioTestCase):
    async def test_close_stops_consumer(self) -> None:
        consumer = MagicMock()
        consumer.stop = AsyncMock()
        src = KafkaStreamingSource(consumer=consumer, parameter_name="x")
        await src.close()
        consumer.stop.assert_called_once()

    async def test_close_without_consumer_is_noop(self) -> None:
        src = KafkaStreamingSource(topic="t", parameter_name="x")
        await src.close()  # no exception
