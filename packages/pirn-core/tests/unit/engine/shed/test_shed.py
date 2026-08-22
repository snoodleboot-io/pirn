"""Unit tests for Shed and CycleDetector."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
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

    def test_child_outside_knot_ids_is_explored(self) -> None:
        """Children absent from ``knot_ids`` are white and get walked."""
        children = {"a": ["ghost"], "ghost": ["a"]}
        self.assertTrue(CycleDetector.detect(["a"], children))

    def test_self_loop(self) -> None:
        self.assertTrue(CycleDetector.detect(["a"], {"a": ["a"]}))

    def test_diamond_is_not_a_cycle(self) -> None:
        """A re-converging path revisits a black node; that is not a cycle."""
        children = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        self.assertFalse(CycleDetector.detect(["a", "b", "c", "d"], children))


class TestCycleDetectorDepth(unittest.TestCase):
    """The walk must not consume a Python frame per graph level.

    It used to recurse, capping usable graph depth at roughly 980 knots. Because
    the engine validates the graph on every run, a deeper chain died with a
    RecursionError before executing anything. ``LoopSubTapestry`` chains
    iterations through parent edges — one level per iteration — so an
    open-ended conversational loop reached that ceiling in normal use.
    See PIR-766, which closes PIR-763.
    """

    DEPTH = 5000

    def test_deep_acyclic_chain(self) -> None:
        ids = [f"n{i}" for i in range(self.DEPTH)]
        children = {f"n{i}": [f"n{i + 1}"] for i in range(self.DEPTH - 1)}
        self.assertFalse(CycleDetector.detect(ids, children))

    def test_deep_cyclic_chain(self) -> None:
        ids = [f"n{i}" for i in range(self.DEPTH)]
        children = {f"n{i}": [f"n{i + 1}"] for i in range(self.DEPTH - 1)}
        children[f"n{self.DEPTH - 1}"] = ["n0"]
        self.assertTrue(CycleDetector.detect(ids, children))


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


class TestShedEntriesAreIdKeyedNotIdentityKeyed(unittest.TestCase):
    """A shed entry need not be the object the caller's graph holds.

    ``Engine._bind_parameters`` swaps each ``Parameter`` for a run-scoped
    ``bound_copy`` under the same ``knot_id`` (PIR-802).  ``Knot.__eq__`` and
    ``__hash__`` are identity, so any shed helper that compares a stored knot
    against a graph knot by ``is`` (or by ``==``) reports a mismatch that is
    not one.  ``Shed.merge_knot`` did exactly that and raised "two distinct
    knots share id" for a perfectly ordinary bound parameter; it was
    unreachable dead code and was deleted (PIR-811).  These pin the contract
    any replacement must honour.
    """

    def _bound_shed(self) -> tuple[Shed, Parameter]:
        with Tapestry():
            param = Parameter("p", int, _config=KnotConfig(id="p"))
            sink = _B(a=param, _config=KnotConfig(id="b"))
        shed = Shed.from_terminals(sink)
        # What Engine._bind_parameters does once per run.
        shed.knots["p"] = param.bound_copy(1)
        return shed, param

    def test_bound_copy_keeps_the_id_but_not_the_identity(self) -> None:
        shed, param = self._bound_shed()
        stored = shed.knot("p")
        self.assertEqual(stored.knot_id, param.knot_id)
        self.assertIsNot(stored, param)
        self.assertNotEqual(stored, param)

    def test_lookups_still_resolve_by_id_after_binding(self) -> None:
        shed, _ = self._bound_shed()
        self.assertIn("p", shed)
        self.assertEqual([e.parent_id for e in shed.parents_of("b")], ["p"])
        self.assertEqual(shed.children_of("p"), ["b"])
        self.assertEqual(shed.topological_order(), ["p", "b"])

    def test_shed_exposes_no_mutation_api(self) -> None:
        """The engine owns post-construction mutation; the shed offers none."""
        public = {
            name
            for name in dir(Shed)
            if not name.startswith("_") and callable(getattr(Shed, name, None))
        }
        self.assertEqual(
            public,
            {
                "children_of",
                "from_terminals",
                "knot",
                "leaves",
                "parents_of",
                "roots",
                "topological_order",
            },
        )
