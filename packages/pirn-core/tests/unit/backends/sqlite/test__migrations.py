"""Tests for apply_migrations SQLite schema migration helper."""

from __future__ import annotations

import sqlite3
import unittest

from pirn.backends.sqlite._migrations import apply_migrations


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE pirn_schema_version "
        "(component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
    )
    return conn


class TestApplyMigrations(unittest.TestCase):
    """apply_migrations advances schema version and calls migration functions."""

    def test_fresh_db_applies_all_migrations(self) -> None:
        conn = _fresh_conn()
        called: list[int] = []

        def _m1(c: sqlite3.Connection) -> None:
            called.append(1)

        def _m2(c: sqlite3.Connection) -> None:
            called.append(2)

        apply_migrations(conn, "test", 2, {1: _m1, 2: _m2})
        self.assertEqual(called, [1, 2])

    def test_records_target_version_in_table(self) -> None:
        conn = _fresh_conn()
        apply_migrations(conn, "test_comp", 3, {})
        row = conn.execute(
            "SELECT version FROM pirn_schema_version WHERE component = 'test_comp'"
        ).fetchone()
        self.assertEqual(row[0], 3)

    def test_existing_version_only_applies_newer_migrations(self) -> None:
        conn = _fresh_conn()
        conn.execute(
            "INSERT INTO pirn_schema_version VALUES ('comp', 1)"
        )
        called: list[int] = []

        def _m1(c: sqlite3.Connection) -> None:
            called.append(1)

        def _m2(c: sqlite3.Connection) -> None:
            called.append(2)

        apply_migrations(conn, "comp", 2, {1: _m1, 2: _m2})
        # Only m2 should be called (v1 already applied)
        self.assertEqual(called, [2])

    def test_already_at_target_version_no_migrations_called(self) -> None:
        conn = _fresh_conn()
        conn.execute(
            "INSERT INTO pirn_schema_version VALUES ('comp', 5)"
        )
        called: list[int] = []
        apply_migrations(conn, "comp", 5, {1: lambda c: called.append(1)})
        self.assertEqual(called, [])

    def test_no_migration_for_version_gap_skips_gracefully(self) -> None:
        conn = _fresh_conn()
        # Only v2 registered; v1 has no migration — should still advance
        called: list[int] = []
        apply_migrations(conn, "comp", 2, {2: lambda c: called.append(2)})
        self.assertEqual(called, [2])
        row = conn.execute(
            "SELECT version FROM pirn_schema_version WHERE component = 'comp'"
        ).fetchone()
        self.assertEqual(row[0], 2)

    def test_empty_migrations_dict_advances_version(self) -> None:
        conn = _fresh_conn()
        apply_migrations(conn, "comp", 3)
        row = conn.execute(
            "SELECT version FROM pirn_schema_version WHERE component = 'comp'"
        ).fetchone()
        self.assertEqual(row[0], 3)

    def test_multiple_components_tracked_independently(self) -> None:
        conn = _fresh_conn()
        apply_migrations(conn, "alpha", 2, {})
        apply_migrations(conn, "beta", 5, {})
        alpha = conn.execute(
            "SELECT version FROM pirn_schema_version WHERE component = 'alpha'"
        ).fetchone()[0]
        beta = conn.execute(
            "SELECT version FROM pirn_schema_version WHERE component = 'beta'"
        ).fetchone()[0]
        self.assertEqual(alpha, 2)
        self.assertEqual(beta, 5)
