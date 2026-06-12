"""Security tests: CRIT-1 — SQLite PRAGMA injection (SqliteConfig validation)."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.sqlite_config import SqliteConfig


class TestJournalModeAllowlist(unittest.TestCase):
    def test_allowed_modes_accepted(self) -> None:
        for mode in ("WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"):
            cfg = SqliteConfig(journal_mode=mode)
            assert cfg.journal_mode == mode

    def test_lowercase_mode_accepted(self) -> None:
        cfg = SqliteConfig(journal_mode="wal")
        assert cfg.journal_mode == "wal"

    def test_injected_journal_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SqliteConfig(journal_mode="WAL; ATTACH '/etc/passwd' AS x; --")

    def test_arbitrary_journal_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SqliteConfig(journal_mode="evil_mode")


class TestPragmaNameAllowlist(unittest.TestCase):
    def test_safe_pragma_name_accepted(self) -> None:
        cfg = SqliteConfig(pragmas=(("busy_timeout", "5000"),))
        assert cfg.pragmas[0][0] == "busy_timeout"

    def test_pragma_name_with_semicolon_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SqliteConfig(pragmas=(("writable_schema; DROP TABLE x; --", "ON"),))

    def test_pragma_name_with_uppercase_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SqliteConfig(pragmas=(("WrItable_schema", "ON"),))

    def test_pragma_name_with_spaces_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SqliteConfig(pragmas=(("busy timeout", "5000"),))

    def test_writable_schema_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SqliteConfig(pragmas=(("WRITABLE_SCHEMA", "ON"),))
