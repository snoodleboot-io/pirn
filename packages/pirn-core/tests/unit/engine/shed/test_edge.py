"""Unit tests for Edge."""

from __future__ import annotations

import unittest

from pirn.engine.shed.edge import Edge


class TestEdge(unittest.TestCase):
    def test_construction(self) -> None:
        e = Edge(child_id="child", parent_id="parent", name="x")
        self.assertEqual(e.child_id, "child")
        self.assertEqual(e.parent_id, "parent")
        self.assertEqual(e.name, "x")

    def test_is_frozen(self) -> None:
        e = Edge(child_id="c", parent_id="p", name="n")
        with self.assertRaises(Exception):
            e.child_id = "other"  # type: ignore

    def test_equality(self) -> None:
        e1 = Edge(child_id="c", parent_id="p", name="n")
        e2 = Edge(child_id="c", parent_id="p", name="n")
        self.assertEqual(e1, e2)

    def test_inequality(self) -> None:
        e1 = Edge(child_id="c", parent_id="p", name="n")
        e2 = Edge(child_id="c", parent_id="p", name="m")
        self.assertNotEqual(e1, e2)
