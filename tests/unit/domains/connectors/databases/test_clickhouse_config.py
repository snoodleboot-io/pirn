"""Tests for :class:`pirn.connectors.databases.clickhouse_config.ClickhouseConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.clickhouse_config import ClickhouseConfig


class TestClickhouseConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = ClickhouseConfig()
        self.assertIsNone(cfg.host)
        self.assertEqual(cfg.port, 8443)
        self.assertIsNone(cfg.username)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.database)
        self.assertTrue(cfg.secure)

    def test_construct_with_fields(self) -> None:
        cfg = ClickhouseConfig(
            host="clickhouse.example.com",
            port=8123,
            username="default",
            password="pass",
            database="analytics",
            secure=False,
        )
        self.assertEqual(cfg.host, "clickhouse.example.com")
        self.assertEqual(cfg.port, 8123)
        self.assertFalse(cfg.secure)

    def test_no_sensitive_fields_declared(self) -> None:
        self.assertEqual(ClickhouseConfig.sensitive_fields, ())

    def test_repr_redacts_password_via_name_pattern(self) -> None:
        cfg = ClickhouseConfig(password="secret-pw")
        text = repr(cfg)
        self.assertNotIn("secret-pw", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = ClickhouseConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
