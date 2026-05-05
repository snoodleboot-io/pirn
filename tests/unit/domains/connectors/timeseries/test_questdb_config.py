"""Tests for :class:`pirn.domains.connectors.timeseries.questdb_config.QuestDBConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.timeseries.questdb_config import QuestDBConfig


class TestQuestDBConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = QuestDBConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.http_port, 9000)
        self.assertEqual(cfg.ilp_port, 9009)
        self.assertEqual(cfg.pg_port, 8812)
        self.assertEqual(cfg.username, "admin")
        self.assertEqual(cfg.password, "")
        self.assertEqual(cfg.database, "qdb")
        self.assertFalse(cfg.tls)

    def test_construct_with_fields(self) -> None:
        cfg = QuestDBConfig(
            host="questdb.example.com",
            username="qdb_user",
            password="qdb-pw",
            tls=True,
        )
        self.assertEqual(cfg.host, "questdb.example.com")
        self.assertTrue(cfg.tls)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", QuestDBConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = QuestDBConfig(password="qdb-secret")
        text = repr(cfg)
        self.assertNotIn("qdb-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = QuestDBConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
