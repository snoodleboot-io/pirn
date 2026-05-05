"""Tests for :class:`pirn.domains.connectors.graph.neo4j_config.Neo4jConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.graph.neo4j_config import Neo4jConfig


class TestNeo4jConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = Neo4jConfig()
        self.assertEqual(cfg.uri, "bolt://localhost:7687")
        self.assertEqual(cfg.user, "neo4j")
        self.assertEqual(cfg.password, "")
        self.assertEqual(cfg.database, "neo4j")
        self.assertEqual(cfg.max_connection_pool_size, 50)
        self.assertEqual(cfg.connection_timeout, 30.0)
        self.assertFalse(cfg.encrypted)

    def test_construct_with_fields(self) -> None:
        cfg = Neo4jConfig(
            uri="neo4j+s://neo4j.example.com:7687",
            user="graph_user",
            password="neo-pw",
            database="mygraph",
            encrypted=True,
        )
        self.assertEqual(cfg.uri, "neo4j+s://neo4j.example.com:7687")
        self.assertTrue(cfg.encrypted)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", Neo4jConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = Neo4jConfig(password="neo4j-secret")
        text = repr(cfg)
        self.assertNotIn("neo4j-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = Neo4jConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.uri = "mutated"  # type: ignore[misc]
