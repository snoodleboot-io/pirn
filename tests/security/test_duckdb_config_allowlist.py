"""Security tests: H-1 — DuckDB dangerous config key allowlist."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.databases.duckdb_config import DuckdbConfig


class TestDuckdbConfigAllowlist(unittest.TestCase):
    def test_safe_keys_accepted(self) -> None:
        cfg = DuckdbConfig(config=(("threads", "4"), ("memory_limit", "1GB")))
        assert cfg.config[0][0] == "threads"

    def test_enable_external_access_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DuckdbConfig(config=(("enable_external_access", "true"),))

    def test_autoinstall_known_extensions_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DuckdbConfig(config=(("autoinstall_known_extensions", "true"),))

    def test_home_directory_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DuckdbConfig(config=(("home_directory", "/tmp/evil"),))

    def test_unknown_key_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DuckdbConfig(config=(("made_up_dangerous_key", "value"),))

    def test_error_message_lists_allowed_keys(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            DuckdbConfig(config=(("bad_key", "v"),))
        assert "threads" in str(ctx.exception)
