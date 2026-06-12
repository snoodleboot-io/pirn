"""Tests for :class:`pirn.connectors.databases.dremio_config.DremioConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.dremio_config import DremioConfig


class TestDremioConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DremioConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 32010)
        self.assertEqual(cfg.username, "dremio")
        self.assertEqual(cfg.password, "")
        self.assertFalse(cfg.tls)
        self.assertEqual(cfg.path, "/")
        self.assertEqual(cfg.connection_timeout, 30.0)

    def test_construct_with_fields(self) -> None:
        cfg = DremioConfig(
            host="dremio.example.com",
            port=32010,
            username="analyst",
            password="pw123",
            tls=True,
            path="/my-space",
            connection_timeout=60.0,
        )
        self.assertEqual(cfg.host, "dremio.example.com")
        self.assertEqual(cfg.username, "analyst")
        self.assertTrue(cfg.tls)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", DremioConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = DremioConfig(password="secret-pw")
        text = repr(cfg)
        self.assertNotIn("secret-pw", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = DremioConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
