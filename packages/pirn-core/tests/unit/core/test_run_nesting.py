"""Unit tests for ``RunNesting`` (ADR agents-speaks-core, WS0)."""

from __future__ import annotations

import unittest

from pirn.core.run_nesting import RunNesting
from pirn.exceptions.nested_run_cycle_error import NestedRunCycleError
from pirn.exceptions.nesting_depth_exceeded_error import NestingDepthExceededError
from pirn.exceptions.pirn_error import PirnError


class TestRootFrame(unittest.TestCase):
    def test_defaults_describe_a_root_run(self) -> None:
        frame = RunNesting()
        self.assertEqual(frame.depth, 0)
        self.assertEqual(frame.run_ids, ())
        self.assertEqual(frame.path, ())
        self.assertIsNone(frame.max_depth)
        self.assertFalse(frame.guarded)

    def test_is_frozen(self) -> None:
        with self.assertRaises(AttributeError):
            RunNesting().depth = 3

    def test_current_outside_a_run_is_the_root_frame(self) -> None:
        self.assertEqual(RunNesting.current(), RunNesting())

    def test_run_path_of_a_root_run(self) -> None:
        self.assertEqual(RunNesting().run_path("r0"), "/r0")


class TestChild(unittest.TestCase):
    def test_increments_depth_and_records_the_parent_run(self) -> None:
        child = RunNesting().child("a.A", "r0")
        self.assertEqual(child.depth, 1)
        self.assertEqual(child.run_ids, ("r0",))
        self.assertEqual(child.path, ("a.A",))

    def test_a_keyless_child_counts_depth_but_not_path(self) -> None:
        child = RunNesting().child("a.A", "r0").child(None, "r1")
        self.assertEqual(child.depth, 2)
        self.assertEqual(child.run_ids, ("r0", "r1"))
        self.assertEqual(child.path, ("a.A",))

    def test_run_path_of_a_nested_run(self) -> None:
        child = RunNesting().child("a.A", "r0").child("b.B", "r1")
        self.assertEqual(child.run_path("r2"), "/r0/r1/r2")

    def test_unguarded_nesting_is_unbounded_and_allows_re_entry(self) -> None:
        frame = RunNesting()
        for i in range(50):
            frame = frame.child("a.A", f"r{i}")
        self.assertEqual(frame.depth, 50)
        self.assertFalse(frame.guarded)


class TestDepthCap(unittest.TestCase):
    def test_own_cap_is_carried_on_the_child(self) -> None:
        child = RunNesting().child("a.A", "r0", max_depth=3)
        self.assertEqual(child.max_depth, 3)
        self.assertTrue(child.guarded)

    def test_a_child_at_the_cap_is_allowed(self) -> None:
        frame = RunNesting(max_depth=2).child("a.A", "r0").child("b.B", "r1")
        self.assertEqual(frame.depth, 2)

    def test_a_child_over_the_cap_is_refused(self) -> None:
        frame = RunNesting(max_depth=2).child("a.A", "r0").child("b.B", "r1")
        with self.assertRaises(NestingDepthExceededError) as caught:
            frame.child("c.C", "r2")
        self.assertEqual(caught.exception.depth, 3)
        self.assertEqual(caught.exception.limit, 2)
        self.assertEqual(caught.exception.path, ("a.A", "b.B"))
        self.assertEqual(caught.exception.key, "c.C")
        self.assertIn("max_nesting_depth=2", str(caught.exception))

    def test_a_keyless_child_over_the_cap_is_refused_too(self) -> None:
        frame = RunNesting(max_depth=1).child("a.A", "r0")
        with self.assertRaises(NestingDepthExceededError) as caught:
            frame.child(None, "r1")
        self.assertIsNone(caught.exception.key)

    def test_the_tighter_cap_wins(self) -> None:
        inherited = RunNesting(max_depth=5)
        self.assertEqual(inherited.child("a.A", "r0", max_depth=2).max_depth, 2)
        self.assertEqual(RunNesting(max_depth=2).child("a.A", "r0", max_depth=5).max_depth, 2)

    def test_a_zero_cap_refuses_any_nesting(self) -> None:
        with self.assertRaises(NestingDepthExceededError):
            RunNesting(max_depth=0).child("a.A", "r0")

    def test_errors_are_pirn_errors(self) -> None:
        self.assertTrue(issubclass(NestingDepthExceededError, PirnError))
        self.assertTrue(issubclass(NestedRunCycleError, PirnError))


class TestCycleGuard(unittest.TestCase):
    def test_re_entering_a_class_on_the_path_is_a_cycle_when_guarded(self) -> None:
        frame = RunNesting(max_depth=10).child("a.A", "r0").child("b.B", "r1")
        with self.assertRaises(NestedRunCycleError) as caught:
            frame.child("a.A", "r2")
        self.assertEqual(caught.exception.key, "a.A")
        self.assertEqual(caught.exception.path, ("a.A", "b.B"))
        self.assertIn("'a.A'", str(caught.exception))

    def test_a_different_class_is_not_a_cycle(self) -> None:
        frame = RunNesting(max_depth=10).child("a.A", "r0")
        self.assertEqual(frame.child("b.B", "r1").path, ("a.A", "b.B"))

    def test_keyless_children_never_form_a_cycle(self) -> None:
        frame = RunNesting(max_depth=10).child("loop.L", "r0")
        frame = frame.child(None, "r1").child(None, "r2")
        self.assertEqual(frame.depth, 3)

    def test_depth_is_checked_before_the_cycle(self) -> None:
        frame = RunNesting(max_depth=1).child("a.A", "r0")
        with self.assertRaises(NestingDepthExceededError):
            frame.child("a.A", "r1")
