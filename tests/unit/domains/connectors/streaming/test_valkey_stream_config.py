"""Tests for :class:`pirn.connectors.streaming.valkey_stream_config.ValkeyStreamConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.streaming.valkey_stream_config import ValkeyStreamConfig


class TestValkeyStreamConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = ValkeyStreamConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 6379)
        self.assertIsNone(cfg.password)
        self.assertFalse(cfg.use_tls)
        self.assertIsNone(cfg.consumer_group)
        self.assertEqual(cfg.consumer_name, "pirn")
        self.assertEqual(cfg.block_ms, 1000)
        self.assertEqual(cfg.count_per_read, 100)

    def test_construct_with_fields(self) -> None:
        cfg = ValkeyStreamConfig(
            host="valkey.example.com",
            port=6380,
            password="valkey-pw",
            use_tls=True,
            consumer_group="my-group",
            consumer_name="worker-1",
            block_ms=500,
            count_per_read=50,
        )
        self.assertEqual(cfg.host, "valkey.example.com")
        self.assertEqual(cfg.consumer_group, "my-group")
        self.assertTrue(cfg.use_tls)

    def test_no_sensitive_fields_declared(self) -> None:
        self.assertEqual(ValkeyStreamConfig.sensitive_fields, ())

    def test_repr_redacts_password_via_name_pattern(self) -> None:
        cfg = ValkeyStreamConfig(password="valkey-secret")
        text = repr(cfg)
        self.assertNotIn("valkey-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = ValkeyStreamConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
