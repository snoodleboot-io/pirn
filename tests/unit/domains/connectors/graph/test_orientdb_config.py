"""Tests for :class:`pirn.domains.connectors.graph.orientdb_config.OrientDBConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.graph.orientdb_config import OrientDBConfig


class TestOrientDBConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = OrientDBConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 2424)
        self.assertEqual(cfg.http_port, 2480)
        self.assertEqual(cfg.user, "root")
        self.assertEqual(cfg.password, "")
        self.assertEqual(cfg.database, "")
        self.assertEqual(cfg.server_version, "")

    def test_construct_with_fields(self) -> None:
        cfg = OrientDBConfig(
            host="orientdb.example.com",
            port=2424,
            http_port=2480,
            user="admin",
            password="orient-pw",
            database="mydb",
            server_version="3.2",
        )
        self.assertEqual(cfg.host, "orientdb.example.com")
        self.assertEqual(cfg.database, "mydb")
        self.assertEqual(cfg.server_version, "3.2")

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", OrientDBConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = OrientDBConfig(password="orient-secret")
        text = repr(cfg)
        self.assertNotIn("orient-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = OrientDBConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
