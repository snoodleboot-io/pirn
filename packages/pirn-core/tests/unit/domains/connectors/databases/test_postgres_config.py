"""Tests for :class:`pirn.connectors.databases.postgres_config.PostgresConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.postgres_config import PostgresConfig


class TestPostgresConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = PostgresConfig()
        self.assertIsNone(cfg.dsn)
        self.assertIsNone(cfg.host)
        self.assertEqual(cfg.port, 5432)
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.database)
        self.assertEqual(cfg.min_size, 1)
        self.assertEqual(cfg.max_size, 10)
        self.assertEqual(cfg.command_timeout, 30.0)
        self.assertEqual(cfg.statement_cache_size, 100)

    def test_construct_with_fields(self) -> None:
        cfg = PostgresConfig(
            host="pg.example.com",
            port=5433,
            user="app",
            password="pg-pw",
            database="mydb",
        )
        self.assertEqual(cfg.host, "pg.example.com")
        self.assertEqual(cfg.port, 5433)

    def test_construct_with_dsn(self) -> None:
        cfg = PostgresConfig(dsn="postgresql://user:pass@host/db")
        self.assertEqual(cfg.dsn, "postgresql://user:pass@host/db")

    def test_repr_redacts_password(self) -> None:
        cfg = PostgresConfig(password="pg-secret")
        text = repr(cfg)
        self.assertNotIn("pg-secret", text)
        self.assertIn("<redacted>", text)

    def test_repr_scrubs_dsn(self) -> None:
        cfg = PostgresConfig(dsn="postgresql://user:pass@host/db")
        text = repr(cfg)
        self.assertNotIn("user:pass@", text)

    def test_frozen(self) -> None:
        cfg = PostgresConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
