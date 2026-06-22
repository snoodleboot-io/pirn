"""Unit tests for Shed and CycleDetector."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.engine.shed.shed import CycleDetector, Shed, detect_cycle
from pirn.engine.shed.shed_error import ShedError
from pirn.nodes.sink import Sink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _A(Source):
    async def process(self, **_: Any) -> int:
        return 1


class _B(Sink):
    async def process(self, a: int, **_: Any) -> None:
        pass


class TestCycleDetector(unittest.TestCase):
    def test_no_cycle_linear(self) -> None:
        children = {"a": ["b"], "b": []}
        self.assertFalse(CycleDetector.detect(["a", "b"], children))

    def test_cycle_detected(self) -> None:
        children = {"a": ["b"], "b": ["a"]}
        self.assertTrue(CycleDetector.detect(["a", "b"], children))

    def test_empty_graph_no_cycle(self) -> None:
        self.assertFalse(CycleDetector.detect([], {}))

    def test_detect_cycle_wrapper(self) -> None:
        self.assertFalse(detect_cycle(["x"], {"x": []}))


class TestShedFromTerminals(unittest.TestCase):
    def test_single_terminal(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
        s = Shed.from_terminals(src)
        self.assertIn("a", s)
        self.assertEqual(len(s), 1)

    def test_two_node_chain(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
            sink = _B(a=src, _config=KnotConfig(id="b"))
        s = Shed.from_terminals(sink)
        self.assertEqual(len(s), 2)
        self.assertIn("a", s)
        self.assertIn("b", s)

    def test_roots_are_sources(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
            sink = _B(a=src, _config=KnotConfig(id="b"))
        s = Shed.from_terminals(sink)
        root_ids = [k.knot_id for k in s.roots()]
        self.assertIn("a", root_ids)

    def test_leaves_are_terminals(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
            sink = _B(a=src, _config=KnotConfig(id="b"))
        s = Shed.from_terminals(sink)
        leaf_ids = [k.knot_id for k in s.leaves()]
        self.assertIn("b", leaf_ids)

    def test_topological_order_is_valid(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
            sink = _B(a=src, _config=KnotConfig(id="b"))
        s = Shed.from_terminals(sink)
        order = s.topological_order()
        self.assertEqual(order.index("a"), 0)
        self.assertEqual(order.index("b"), 1)

    def test_contains_operator(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
        s = Shed.from_terminals(src)
        self.assertIn("a", s)
        self.assertNotIn("missing", s)

    def test_knot_accessor(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
        s = Shed.from_terminals(src)
        self.assertIs(s.knot("a"), src)

    def test_knot_accessor_raises_for_unknown(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
        s = Shed.from_terminals(src)
        with self.assertRaises(ShedError):
            s.knot("missing")

    def test_parents_of(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
            sink = _B(a=src, _config=KnotConfig(id="b"))
        s = Shed.from_terminals(sink)
        parents = s.parents_of("b")
        self.assertEqual(len(parents), 1)
        self.assertEqual(parents[0].parent_id, "a")

    def test_children_of(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
            sink = _B(a=src, _config=KnotConfig(id="b"))
        s = Shed.from_terminals(sink)
        self.assertIn("b", s.children_of("a"))

    def test_accepts_single_knot_not_list(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
        s = Shed.from_terminals(src)
        self.assertEqual(len(s), 1)


class TestShedMergeKnot(unittest.TestCase):
    def test_merge_adds_new_knot(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
        s = Shed.from_terminals(src)

        with Tapestry():
            src2 = _A(_config=KnotConfig(id="a2"))
        added = s.merge_knot(src2)
        self.assertTrue(added)
        self.assertIn("a2", s)

    def test_merge_same_knot_is_noop(self) -> None:
        with Tapestry():
            src = _A(_config=KnotConfig(id="a"))
        s = Shed.from_terminals(src)
        added = s.merge_knot(src)
        self.assertFalse(added)
