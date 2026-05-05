"""Tests for TapestrySnapshot value object."""

from __future__ import annotations

import unittest

from pirn.backends.base.tapestry_snapshot import TapestrySnapshot


class TestTapestrySnapshot(unittest.TestCase):
    """TapestrySnapshot is a frozen Pydantic model used as an immutable view."""

    def test_empty_snapshot_has_empty_knot_ids(self) -> None:
        snap = TapestrySnapshot()
        self.assertEqual(snap.knot_ids, [])

    def test_snapshot_stores_provided_knot_ids(self) -> None:
        snap = TapestrySnapshot(knot_ids=["a", "b", "c"])
        self.assertEqual(snap.knot_ids, ["a", "b", "c"])

    def test_snapshot_is_frozen_cannot_mutate(self) -> None:
        snap = TapestrySnapshot(knot_ids=["x"])
        with self.assertRaises(Exception):
            snap.knot_ids = ["y"]  # type: ignore[misc]

    def test_snapshot_equality_by_value(self) -> None:
        a = TapestrySnapshot(knot_ids=["a", "b"])
        b = TapestrySnapshot(knot_ids=["a", "b"])
        self.assertEqual(a, b)

    def test_snapshot_inequality(self) -> None:
        a = TapestrySnapshot(knot_ids=["a"])
        b = TapestrySnapshot(knot_ids=["b"])
        self.assertNotEqual(a, b)

    def test_snapshot_knot_ids_default_factory_not_shared(self) -> None:
        a = TapestrySnapshot()
        b = TapestrySnapshot()
        # Each instance gets its own list
        self.assertIsNot(a.knot_ids, b.knot_ids)

    def test_snapshot_preserves_order(self) -> None:
        ids = ["z", "a", "m", "b"]
        snap = TapestrySnapshot(knot_ids=ids)
        self.assertEqual(snap.knot_ids, ids)
