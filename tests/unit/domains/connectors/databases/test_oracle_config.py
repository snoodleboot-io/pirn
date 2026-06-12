"""Tests for :class:`pirn.connectors.databases.oracle_config.OracleConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.oracle_config import OracleConfig


class TestOracleConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = OracleConfig()
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.dsn)
        self.assertIsNone(cfg.wallet_location)
        self.assertEqual(cfg.min_size, 1)
        self.assertEqual(cfg.max_size, 4)

    def test_construct_with_fields(self) -> None:
        cfg = OracleConfig(
            user="oracle_user",
            password="oracle-pw",
            dsn="host:1521/ORCLPDB1",
            wallet_location="/oracle/wallet",
            min_size=2,
            max_size=8,
        )
        self.assertEqual(cfg.user, "oracle_user")
        self.assertEqual(cfg.dsn, "host:1521/ORCLPDB1")

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", OracleConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = OracleConfig(password="oracle-secret")
        text = repr(cfg)
        self.assertNotIn("oracle-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = OracleConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.user = "mutated"  # type: ignore[misc]
