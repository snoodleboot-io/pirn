"""Tests for :class:`pirn.domains.connectors.timeseries.timescaledb_config.TimescaleDBConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.timeseries.timescaledb_config import TimescaleDBConfig


class TestTimescaleDBConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = TimescaleDBConfig()
        self.assertIsNone(cfg.dsn)
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 5432)
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.database)
        self.assertEqual(cfg.schema, "public")
        self.assertEqual(cfg.min_size, 1)
        self.assertEqual(cfg.max_size, 10)
        self.assertEqual(cfg.command_timeout, 30.0)

    def test_construct_with_fields(self) -> None:
        cfg = TimescaleDBConfig(
            host="tsdb.example.com",
            port=5433,
            user="ts_user",
            password="ts-pw",
            database="metrics",
            schema="timeseries",
        )
        self.assertEqual(cfg.host, "tsdb.example.com")
        self.assertEqual(cfg.schema, "timeseries")

    def test_construct_with_dsn(self) -> None:
        cfg = TimescaleDBConfig(dsn="postgresql://user:pass@host/db")
        self.assertEqual(cfg.dsn, "postgresql://user:pass@host/db")

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", TimescaleDBConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = TimescaleDBConfig(password="ts-secret")
        text = repr(cfg)
        self.assertNotIn("ts-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = TimescaleDBConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
