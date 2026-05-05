"""Tests for :class:`pirn.domains.connectors.databases.redshift_config.RedshiftConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.databases.redshift_config import RedshiftConfig


class TestRedshiftConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = RedshiftConfig()
        self.assertIsNone(cfg.dsn)
        self.assertIsNone(cfg.host)
        self.assertEqual(cfg.port, 5439)
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.database)
        self.assertEqual(cfg.min_size, 1)
        self.assertEqual(cfg.max_size, 10)
        self.assertEqual(cfg.command_timeout, 30.0)
        self.assertEqual(cfg.statement_cache_size, 0)

    def test_construct_with_fields(self) -> None:
        cfg = RedshiftConfig(
            host="my-cluster.abc.us-east-1.redshift.amazonaws.com",
            port=5439,
            user="rs_user",
            password="rs-pw",
            database="warehouse",
        )
        self.assertEqual(cfg.host, "my-cluster.abc.us-east-1.redshift.amazonaws.com")
        self.assertEqual(cfg.database, "warehouse")

    def test_statement_cache_disabled_by_default(self) -> None:
        cfg = RedshiftConfig()
        self.assertEqual(cfg.statement_cache_size, 0)

    def test_repr_redacts_password(self) -> None:
        cfg = RedshiftConfig(password="rs-secret")
        text = repr(cfg)
        self.assertNotIn("rs-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = RedshiftConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
