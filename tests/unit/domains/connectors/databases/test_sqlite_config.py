"""Tests for :class:`pirn.connectors.databases.sqlite_config.SqliteConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.sqlite_config import SqliteConfig


class TestSqliteConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = SqliteConfig()
        self.assertEqual(cfg.database, ":memory:")
        self.assertEqual(cfg.timeout, 5.0)
        self.assertEqual(cfg.journal_mode, "WAL")
        self.assertEqual(cfg.pragmas, ())

    def test_construct_with_fields(self) -> None:
        cfg = SqliteConfig(
            database="/data/db.sqlite",
            timeout=10.0,
            journal_mode="DELETE",
            pragmas=(("foreign_keys", "ON"),),
        )
        self.assertEqual(cfg.database, "/data/db.sqlite")
        self.assertEqual(cfg.timeout, 10.0)
        self.assertEqual(cfg.journal_mode, "DELETE")
        self.assertEqual(len(cfg.pragmas), 1)

    def test_no_sensitive_fields(self) -> None:
        self.assertEqual(SqliteConfig.sensitive_fields, ())

    def test_pragmas_defaults_to_empty_tuple(self) -> None:
        cfg1 = SqliteConfig()
        cfg2 = SqliteConfig()
        self.assertEqual(cfg1.pragmas, ())
        self.assertEqual(cfg2.pragmas, ())

    def test_frozen(self) -> None:
        cfg = SqliteConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.database = "mutated"  # type: ignore[misc]
