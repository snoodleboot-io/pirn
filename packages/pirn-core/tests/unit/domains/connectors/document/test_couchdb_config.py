"""Tests for :class:`pirn.connectors.document.couchdb_config.CouchDBConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.document.couchdb_config import CouchDBConfig


class TestCouchDBConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = CouchDBConfig()
        self.assertEqual(cfg.url, "http://localhost:5984")
        self.assertEqual(cfg.username, "admin")
        self.assertEqual(cfg.password, "")
        self.assertEqual(cfg.database, "")
        self.assertTrue(cfg.verify_ssl)

    def test_construct_with_fields(self) -> None:
        cfg = CouchDBConfig(
            url="https://couch.example.com:5984",
            username="couchuser",
            password="couch-pw",
            database="mydb",
            verify_ssl=False,
        )
        self.assertEqual(cfg.url, "https://couch.example.com:5984")
        self.assertEqual(cfg.database, "mydb")
        self.assertFalse(cfg.verify_ssl)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", CouchDBConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = CouchDBConfig(password="couch-secret")
        text = repr(cfg)
        self.assertNotIn("couch-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = CouchDBConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.url = "mutated"  # type: ignore[misc]
