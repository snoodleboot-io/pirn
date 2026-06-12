"""Tests for :class:`pirn.connectors.databases.mysql_config.MySQLConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.mysql_config import MySQLConfig


class TestMySQLConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = MySQLConfig()
        self.assertIsNone(cfg.host)
        self.assertEqual(cfg.port, 3306)
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.database)
        self.assertEqual(cfg.charset, "utf8mb4")
        self.assertEqual(cfg.min_size, 1)
        self.assertEqual(cfg.max_size, 10)

    def test_construct_with_fields(self) -> None:
        cfg = MySQLConfig(
            host="mysql.example.com",
            port=3307,
            user="app_user",
            password="my-pw",
            database="app_db",
            charset="utf8",
            min_size=2,
            max_size=20,
        )
        self.assertEqual(cfg.host, "mysql.example.com")
        self.assertEqual(cfg.port, 3307)
        self.assertEqual(cfg.charset, "utf8")

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", MySQLConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = MySQLConfig(password="mysql-secret")
        text = repr(cfg)
        self.assertNotIn("mysql-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = MySQLConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
