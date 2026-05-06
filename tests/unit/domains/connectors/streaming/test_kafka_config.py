"""Tests for :class:`pirn.domains.connectors.streaming.kafka_config.KafkaConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.streaming.kafka_config import KafkaConfig


class TestKafkaConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = KafkaConfig()
        self.assertEqual(cfg.bootstrap_servers, "localhost:9092")
        self.assertEqual(cfg.client_id, "pirn")
        self.assertIsNone(cfg.group_id)
        self.assertEqual(cfg.security_protocol, "PLAINTEXT")
        self.assertIsNone(cfg.sasl_mechanism)
        self.assertIsNone(cfg.sasl_username)
        self.assertIsNone(cfg.sasl_password)
        self.assertIsNone(cfg.ssl_cafile)
        self.assertEqual(cfg.extra_producer_config, ())
        self.assertEqual(cfg.extra_consumer_config, ())

    def test_construct_with_fields(self) -> None:
        cfg = KafkaConfig(
            bootstrap_servers="kafka1:9092,kafka2:9092",
            client_id="my-app",
            group_id="my-group",
            security_protocol="SASL_SSL",
            sasl_mechanism="PLAIN",
            sasl_username="kafka-user",
            sasl_password="kafka-pass",
        )
        self.assertEqual(cfg.bootstrap_servers, "kafka1:9092,kafka2:9092")
        self.assertEqual(cfg.group_id, "my-group")
        self.assertEqual(cfg.security_protocol, "SASL_SSL")

    def test_repr_redacts_password(self) -> None:
        cfg = KafkaConfig(sasl_password="kafka-secret")
        text = repr(cfg)
        self.assertNotIn("kafka-secret", text)
        self.assertIn("<redacted>", text)

    def test_extra_configs_default_to_empty(self) -> None:
        cfg1 = KafkaConfig()
        cfg2 = KafkaConfig()
        self.assertEqual(cfg1.extra_producer_config, ())
        self.assertEqual(cfg2.extra_consumer_config, ())

    def test_frozen(self) -> None:
        cfg = KafkaConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.bootstrap_servers = "mutated"  # type: ignore[misc]
