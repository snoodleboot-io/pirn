"""Tests for TapestryGraph."""

from __future__ import annotations

import unittest

from pirn.viz._tapestry_graph import TapestryGraph


class TestTapestryGraphConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        g = TapestryGraph(name="my_pipe", source="pipe.py")
        self.assertEqual(g.name, "my_pipe")
        self.assertEqual(g.source, "pipe.py")
        self.assertEqual(g.nodes, [])
        self.assertEqual(g.edges, [])
        self.assertIsNone(g.error)

    def test_with_nodes_and_edges(self) -> None:
        g = TapestryGraph(
            name="p",
            source="p.yaml",
            nodes=[{"id": "a"}, {"id": "b"}],
            edges=[{"source": "a", "target": "b"}],
        )
        self.assertEqual(len(g.nodes), 2)
        self.assertEqual(len(g.edges), 1)

    def test_with_error(self) -> None:
        g = TapestryGraph(name="bad", source="bad.yaml", error="parse error: unexpected token")
        self.assertEqual(g.error, "parse error: unexpected token")

    def test_to_dict_all_fields(self) -> None:
        g = TapestryGraph(
            name="p",
            source="p.yaml",
            nodes=[{"id": "n1"}],
            edges=[{"source": "n1", "target": "n2"}],
        )
        d = g.to_dict()
        self.assertEqual(d["name"], "p")
        self.assertEqual(d["source"], "p.yaml")
        self.assertEqual(d["nodes"], [{"id": "n1"}])
        self.assertEqual(d["edges"], [{"source": "n1", "target": "n2"}])
        self.assertIsNone(d["error"])

    def test_to_dict_with_error(self) -> None:
        g = TapestryGraph(name="x", source="x.py", error="boom")
        self.assertEqual(g.to_dict()["error"], "boom")
