"""Tests for :class:`pirn.domains.connectors.streaming.rabbitmq_config.RabbitMQConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.streaming.rabbitmq_config import RabbitMQConfig


class TestRabbitMQConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = RabbitMQConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 5672)
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertEqual(cfg.vhost, "/")
        self.assertFalse(cfg.ssl)

    def test_construct_with_fields(self) -> None:
        cfg = RabbitMQConfig(
            host="rabbitmq.example.com",
            port=5671,
            user="rabbit_user",
            password="rabbit-pw",
            vhost="/my-vhost",
            ssl=True,
        )
        self.assertEqual(cfg.host, "rabbitmq.example.com")
        self.assertTrue(cfg.ssl)
        self.assertEqual(cfg.vhost, "/my-vhost")

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", RabbitMQConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = RabbitMQConfig(password="rabbit-secret")
        text = repr(cfg)
        self.assertNotIn("rabbit-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = RabbitMQConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
