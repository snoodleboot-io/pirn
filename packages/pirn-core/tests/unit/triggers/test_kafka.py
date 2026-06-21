"""Unit tests for KafkaTrigger."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.core.run_request import RunRequest
from pirn.triggers.kafka import KafkaTrigger


def _mock_msg(value: bytes) -> MagicMock:
    msg = MagicMock()
    msg.value = value
    return msg


class TestKafkaTriggerConstruction(unittest.TestCase):
    def test_requires_consumer_or_topic(self) -> None:
        with self.assertRaisesRegex(TypeError, "consumer"):
            KafkaTrigger()

    def test_accepts_consumer(self) -> None:
        consumer = MagicMock()
        t = KafkaTrigger(consumer=consumer)
        self.assertIsNotNone(t)

    def test_accepts_topic(self) -> None:
        t = KafkaTrigger(topic="my-topic")
        self.assertIsNotNone(t)

    def test_name(self) -> None:
        t = KafkaTrigger(topic="t")
        self.assertEqual(t.name, "KafkaTrigger")


class TestKafkaTriggerDefaultBuilder(unittest.TestCase):
    def _builder(self) -> callable:
        return KafkaTrigger._KafkaTrigger__default_request_builder

    def test_decodes_json_bytes(self) -> None:
        msg = _mock_msg(b'{"x":1}')
        req = self._builder()(msg)
        self.assertIsInstance(req, RunRequest)
        self.assertEqual(req.parameters["x"], 1)

    def test_decodes_json_string(self) -> None:
        msg = MagicMock()
        msg.value = '{"y":2}'
        req = self._builder()(msg)
        self.assertEqual(req.parameters["y"], 2)

    def test_rejects_non_dict_payload(self) -> None:
        msg = _mock_msg(b'"just_a_string"')
        with self.assertRaises(TypeError):
            self._builder()(msg)


class TestKafkaTriggerClose(unittest.IsolatedAsyncioTestCase):
    async def test_close_stops_consumer(self) -> None:
        consumer = MagicMock()
        consumer.stop = AsyncMock()
        trigger = KafkaTrigger(consumer=consumer)
        await trigger.close()
        consumer.stop.assert_called_once()

    async def test_close_without_consumer_is_noop(self) -> None:
        trigger = KafkaTrigger(topic="t")
        await trigger.close()  # no exception
