"""Tests for :class:`pirn.connectors.graph.memgraph_config.MemgraphConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.graph.memgraph_config import MemgraphConfig


class TestMemgraphConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = MemgraphConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 7687)
        self.assertEqual(cfg.username, "")
        self.assertEqual(cfg.password, "")
        self.assertEqual(cfg.database, "")
        self.assertFalse(cfg.encrypted)
        self.assertEqual(cfg.client_name, "pirn-memgraph")

    def test_construct_with_fields(self) -> None:
        cfg = MemgraphConfig(
            host="memgraph.example.com",
            port=7688,
            username="mg_user",
            password="mg-pw",
            encrypted=True,
        )
        self.assertEqual(cfg.host, "memgraph.example.com")
        self.assertTrue(cfg.encrypted)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", MemgraphConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = MemgraphConfig(password="mg-secret")
        text = repr(cfg)
        self.assertNotIn("mg-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = MemgraphConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
