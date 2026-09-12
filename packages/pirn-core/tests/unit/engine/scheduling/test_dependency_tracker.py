"""Unit tests for DependencyTracker."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.engine.scheduling.dependency_tracker import DependencyTracker
from pirn.engine.shed.edge import Edge
from pirn.engine.shed.shed import Shed


@knot
async def _one(x: Any) -> Any:
    return x


@knot
async def _two(x: Any, y: Any) -> Any:
    return (x, y)


def _param(knot_id: str) -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id=knot_id))


def _diamond() -> Shed:
    """p -> a, p -> b, (a, b) -> d, plus a second root q -> c."""
    p = _param("p")
    a = _one(x=p, _config=KnotConfig(id="a"))
    b = _one(x=p, _config=KnotConfig(id="b"))
    d = _two(x=a, y=b, _config=KnotConfig(id="d"))
    c = _one(x=_param("q"), _config=KnotConfig(id="c"))
    return Shed.from_terminals([d, c])


def _add_to_shed(shed: Shed, new: Knot) -> None:
    """Insert *new* into *shed* the way ``Engine._merge_new_knots`` does."""
    shed.knots[new.knot_id] = new
    shed.children_by_parent.setdefault(new.knot_id, [])
    edges = []
    for name, parent in new.parents.items():
        edges.append(Edge(child_id=new.knot_id, parent_id=parent.knot_id, name=name))
        shed.children_by_parent.setdefault(parent.knot_id, []).append(new.knot_id)
    shed.edges_by_child[new.knot_id] = edges


class TestReadiness(unittest.TestCase):
    def test_roots_are_initially_ready_in_topological_order(self) -> None:
        # Arrange
        tracker = DependencyTracker(_diamond())

        # Act
        ready = tracker.initially_ready()

        # Assert
        self.assertEqual(ready, ["p", "q"])

    def test_resolving_the_only_parent_releases_each_child(self) -> None:
        # Arrange
        tracker = DependencyTracker(_diamond())

        # Act
        released = tracker.resolve("p")

        # Assert
        self.assertEqual(released, ["a", "b"])

    def test_a_child_waits_for_every_parent(self) -> None:
        # Arrange
        tracker = DependencyTracker(_diamond())
        tracker.resolve("p")

        # Act
        after_a = tracker.resolve("a")
        after_b = tracker.resolve("b")

        # Assert
        self.assertEqual(after_a, [])
        self.assertEqual(after_b, ["d"])

    def test_two_edges_from_one_parent_release_the_child_once(self) -> None:
        # Arrange
        p = _param("p")
        both = _two(x=p, y=p, _config=KnotConfig(id="both"))
        tracker = DependencyTracker(Shed.from_terminals([both]))

        # Act
        released = tracker.resolve("p")

        # Assert
        self.assertEqual(released, ["both"])

    def test_the_ready_set_excludes_resolved_knots(self) -> None:
        # Arrange
        tracker = DependencyTracker(_diamond())
        tracker.resolve("p")

        # Act
        ready = tracker.initially_ready()

        # Assert
        self.assertEqual(ready, ["a", "b", "q"])


class TestCoordinates(unittest.TestCase):
    def test_level_is_one_past_the_deepest_parent(self) -> None:
        # Arrange
        p = _param("p")
        a = _one(x=p, _config=KnotConfig(id="a"))
        b = _one(x=a, _config=KnotConfig(id="b"))
        lopsided = _two(x=p, y=b, _config=KnotConfig(id="z"))

        # Act
        tracker = DependencyTracker(Shed.from_terminals([lopsided]))

        # Assert
        self.assertEqual([tracker.level(k) for k in ("p", "a", "b", "z")], [0, 1, 2, 3])

    def test_topo_index_follows_the_shed_topological_order(self) -> None:
        # Arrange
        shed = _diamond()

        # Act
        tracker = DependencyTracker(shed)

        # Assert
        order = shed.topological_order()
        self.assertEqual([tracker.topo_index(k) for k in order], list(range(len(order))))

    def test_is_tracked_reports_membership(self) -> None:
        # Arrange / Act
        tracker = DependencyTracker(_diamond())

        # Assert
        self.assertTrue(tracker.is_tracked("d"))
        self.assertFalse(tracker.is_tracked("nope"))


class TestSortKey(unittest.TestCase):
    def test_orders_by_level_before_topological_index(self) -> None:
        # Arrange: topologically q comes after d, but q is a root (level 0)
        # and d is at level 2.
        tracker = DependencyTracker(_diamond())

        # Act
        ordered = sorted(["d", "c", "a", "q", "p", "b"], key=lambda k: tracker.sort_key(k, True))

        # Assert
        self.assertEqual(ordered, ["p", "q", "a", "b", "c", "d"])

    def test_within_a_level_undispatched_knots_come_first(self) -> None:
        # Arrange
        tracker = DependencyTracker(_diamond())

        # Act
        ordered = sorted(["a", "b"], key=lambda k: tracker.sort_key(k, k == "a"))

        # Assert
        self.assertEqual(ordered, ["b", "a"])

    def test_an_unknown_knot_sorts_after_every_tracked_knot(self) -> None:
        # Arrange
        tracker = DependencyTracker(_diamond())

        # Act
        ordered = sorted(["stranger", "d", "p"], key=lambda k: tracker.sort_key(k, False))

        # Assert
        self.assertEqual(ordered, ["p", "d", "stranger"])


class TestMerge(unittest.TestCase):
    def test_newcomer_of_a_resolved_parent_is_ready_at_once(self) -> None:
        # Arrange
        shed = _diamond()
        tracker = DependencyTracker(shed)
        tracker.resolve("p")
        tracker.resolve("a")
        _add_to_shed(shed, _one(x=shed.knot("a"), _config=KnotConfig(id="late")))

        # Act
        ready = tracker.merge({"late"}, {})

        # Assert
        self.assertEqual(ready, ["late"])
        self.assertEqual(tracker.level("late"), 2)

    def test_newcomer_of_an_unresolved_parent_waits_for_it(self) -> None:
        # Arrange
        shed = _diamond()
        tracker = DependencyTracker(shed)
        _add_to_shed(shed, _one(x=shed.knot("d"), _config=KnotConfig(id="late")))

        # Act
        ready = tracker.merge({"late"}, {})
        tracker.resolve("p")
        tracker.resolve("a")
        tracker.resolve("b")
        released = tracker.resolve("d")

        # Assert
        self.assertEqual(ready, [])
        self.assertEqual(released, ["late"])

    def test_floor_places_a_parentless_newcomer(self) -> None:
        # Arrange
        shed = _diamond()
        tracker = DependencyTracker(shed)
        _add_to_shed(shed, _param("late"))

        # Act
        ready = tracker.merge({"late"}, {"late": 2})

        # Assert
        self.assertEqual(ready, ["late"])
        self.assertEqual(tracker.level("late"), 2)

    def test_a_parent_deeper_than_the_floor_wins(self) -> None:
        # Arrange
        shed = _diamond()
        tracker = DependencyTracker(shed)
        _add_to_shed(shed, _one(x=shed.knot("d"), _config=KnotConfig(id="late")))

        # Act
        tracker.merge({"late"}, {"late": 1})

        # Assert
        self.assertEqual(tracker.level("late"), 3)

    def test_newcomers_chained_to_each_other_merge_together(self) -> None:
        # Arrange
        shed = _diamond()
        tracker = DependencyTracker(shed)
        tracker.resolve("q")
        first = _one(x=shed.knot("q"), _config=KnotConfig(id="n1"))
        second = _one(x=first, _config=KnotConfig(id="n2"))
        _add_to_shed(shed, first)
        _add_to_shed(shed, second)

        # Act
        ready = tracker.merge({"n1", "n2"}, {"n1": 1, "n2": 1})
        released = tracker.resolve("n1")

        # Assert
        self.assertEqual(ready, ["n1"])
        self.assertEqual(released, ["n2"])
        self.assertEqual(tracker.level("n2"), 2)

    def test_merge_reindexes_topological_positions(self) -> None:
        # Arrange
        shed = _diamond()
        tracker = DependencyTracker(shed)
        _add_to_shed(shed, _param("aaa"))

        # Act
        tracker.merge({"aaa"}, {})

        # Assert
        order = shed.topological_order()
        self.assertEqual([tracker.topo_index(k) for k in order], list(range(len(order))))

    def test_a_knot_already_tracked_is_not_reset(self) -> None:
        # Arrange
        shed = _diamond()
        tracker = DependencyTracker(shed)
        tracker.resolve("p")

        # Act
        ready = tracker.merge({"a"}, {"a": 5})

        # Assert
        self.assertEqual(ready, [])
        self.assertEqual(tracker.level("a"), 1)
