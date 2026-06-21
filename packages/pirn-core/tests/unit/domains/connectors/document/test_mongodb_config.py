"""Tests for :class:`pirn.connectors.document.mongodb_config.MongoDBConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.document.mongodb_config import MongoDBConfig


class TestMongoDBConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = MongoDBConfig()
        self.assertEqual(cfg.uri, "mongodb://localhost:27017")
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 27017)
        self.assertIsNone(cfg.username)
        self.assertIsNone(cfg.password)
        self.assertEqual(cfg.database, "")
        self.assertEqual(cfg.auth_source, "admin")
        self.assertFalse(cfg.tls)
        self.assertEqual(cfg.max_pool_size, 100)
        self.assertEqual(cfg.server_selection_timeout_ms, 5000)

    def test_construct_with_fields(self) -> None:
        cfg = MongoDBConfig(
            uri="mongodb+srv://user:pass@cluster.mongodb.net/mydb",
            database="mydb",
            tls=True,
        )
        self.assertEqual(cfg.database, "mydb")
        self.assertTrue(cfg.tls)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", MongoDBConfig.sensitive_fields)
        self.assertIn("uri", MongoDBConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = MongoDBConfig(password="mongo-secret")
        text = repr(cfg)
        self.assertNotIn("mongo-secret", text)
        self.assertIn("<redacted>", text)

    def test_repr_redacts_uri(self) -> None:
        cfg = MongoDBConfig(uri="mongodb://user:pass@host/db")
        text = repr(cfg)
        self.assertNotIn("user:pass@host", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = MongoDBConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
