"""Tests for :class:`pirn.domains.connectors.timeseries.kdb_config.KdbConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.timeseries.kdb_config import KdbConfig


class TestKdbConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = KdbConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 5000)
        self.assertEqual(cfg.username, "")
        self.assertEqual(cfg.password, "")
        self.assertEqual(cfg.timeout, 30.0)
        self.assertFalse(cfg.tls)

    def test_construct_with_fields(self) -> None:
        cfg = KdbConfig(
            host="kdb.example.com",
            port=5001,
            username="kdb_user",
            password="kdb-pw",
            timeout=60.0,
            tls=True,
        )
        self.assertEqual(cfg.host, "kdb.example.com")
        self.assertTrue(cfg.tls)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", KdbConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = KdbConfig(password="kdb-secret")
        text = repr(cfg)
        self.assertNotIn("kdb-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = KdbConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
