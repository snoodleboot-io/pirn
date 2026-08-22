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

    def test_construct_with_fields(self) -> None:
        cfg = OracleConfig(
            user="oracle_user",
            password="oracle-pw",
            dsn="host:1521/ORCLPDB1",
            wallet_location="/oracle/wallet",
        )
        self.assertEqual(cfg.user, "oracle_user")
        self.assertEqual(cfg.dsn, "host:1521/ORCLPDB1")

    def test_has_no_pool_size_fields(self) -> None:
        # OraclePool holds ONE connection for its lifetime, so bounds would be
        # inert. They existed and were passed to `oracledb.create_pool`, whose
        # result had no `cursor()` — so the path raised on every statement and
        # was never reachable. Removed with the fix (PIR-824); this pins that
        # they do not quietly return.
        for field in ("min_size", "max_size"):
            self.assertFalse(hasattr(OracleConfig(), field))

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
