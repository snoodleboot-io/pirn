"""Tests for :class:`RabbitMQPlainMessage`."""

from __future__ import annotations

import unittest

from pirn.connectors.streaming.rabbitmq_plain_message import (
    RabbitMQPlainMessage,
)


class TestRabbitMQPlainMessage(unittest.TestCase):
    def test_body_stored(self) -> None:
        msg = RabbitMQPlainMessage(body=b"payload", key=None, headers=None)
        self.assertEqual(msg.body, b"payload")

    def test_key_decoded_to_correlation_id(self) -> None:
        msg = RabbitMQPlainMessage(body=b"x", key=b"corr-123", headers=None)
        self.assertEqual(msg.correlation_id, "corr-123")

    def test_key_none_gives_none_correlation_id(self) -> None:
        msg = RabbitMQPlainMessage(body=b"x", key=None, headers=None)
        self.assertIsNone(msg.correlation_id)

    def test_headers_stored(self) -> None:
        msg = RabbitMQPlainMessage(
            body=b"x", key=None, headers={"x-retry": b"1"}
        )
        self.assertEqual(msg.headers, {"x-retry": b"1"})

    def test_none_headers_stored_as_none(self) -> None:
        msg = RabbitMQPlainMessage(body=b"x", key=None, headers=None)
        self.assertIsNone(msg.headers)
