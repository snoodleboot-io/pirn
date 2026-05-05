"""Tests for :class:`pirn.domains.connectors.document.arangodb_config.ArangoDBConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.document.arangodb_config import ArangoDBConfig


class TestArangoDBConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = ArangoDBConfig()
        self.assertEqual(cfg.url, "http://localhost:8529")
        self.assertEqual(cfg.username, "root")
        self.assertEqual(cfg.password, "")
        self.assertEqual(cfg.database, "_system")
        self.assertTrue(cfg.verify_ssl)
        self.assertEqual(cfg.connection_timeout, 30.0)

    def test_construct_with_fields(self) -> None:
        cfg = ArangoDBConfig(
            url="https://arango.example.com:8529",
            username="admin",
            password="secret",
            database="mydb",
            verify_ssl=False,
            connection_timeout=60.0,
        )
        self.assertEqual(cfg.url, "https://arango.example.com:8529")
        self.assertEqual(cfg.database, "mydb")
        self.assertFalse(cfg.verify_ssl)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", ArangoDBConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = ArangoDBConfig(password="arango-secret")
        text = repr(cfg)
        self.assertNotIn("arango-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = ArangoDBConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.url = "mutated"  # type: ignore[misc]
