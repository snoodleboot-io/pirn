"""Tests for :class:`pirn.domains.connectors.databases.duckdb_config.DuckdbConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.databases.duckdb_config import DuckdbConfig


class TestDuckdbConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DuckdbConfig()
        self.assertEqual(cfg.database, ":memory:")
        self.assertFalse(cfg.read_only)
        self.assertEqual(cfg.config, ())

    def test_construct_with_fields(self) -> None:
        cfg = DuckdbConfig(
            database="/data/db.duckdb",
            read_only=True,
            config=(("threads", "4"), ("memory_limit", "4GB")),
        )
        self.assertEqual(cfg.database, "/data/db.duckdb")
        self.assertTrue(cfg.read_only)
        self.assertEqual(len(cfg.config), 2)

    def test_no_sensitive_fields(self) -> None:
        self.assertEqual(DuckdbConfig.sensitive_fields, ())

    def test_frozen(self) -> None:
        cfg = DuckdbConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.database = "mutated"  # type: ignore[misc]

    def test_config_defaults_to_empty_tuple(self) -> None:
        cfg1 = DuckdbConfig()
        cfg2 = DuckdbConfig()
        self.assertEqual(cfg1.config, ())
        self.assertEqual(cfg2.config, ())
