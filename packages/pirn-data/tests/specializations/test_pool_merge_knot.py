"""Tests for :class:`PoolMergeKnot`'s row-classification helpers."""

from __future__ import annotations

import unittest

from pirn_data.specializations.pool_merge_knot import PoolMergeKnot


class TestIndexRowsByKey(unittest.TestCase):
    def test_indexes_by_single_key_column(self) -> None:
        rows = [(1, "alice"), (2, "bob")]
        indexed = PoolMergeKnot._index_rows_by_key(rows, key_indices=(0,))
        assert indexed == {(1,): (1, "alice"), (2,): (2, "bob")}

    def test_later_duplicate_key_wins(self) -> None:
        rows = [(1, "alice"), (1, "alice-2")]
        indexed = PoolMergeKnot._index_rows_by_key(rows, key_indices=(0,))
        assert indexed == {(1,): (1, "alice-2")}

    def test_empty_rows_give_empty_index(self) -> None:
        assert PoolMergeKnot._index_rows_by_key([], key_indices=(0,)) == {}


class TestValidateRowWidth(unittest.TestCase):
    def test_accepts_matching_width(self) -> None:
        PoolMergeKnot._validate_row_width("Example", (1, "alice"), ("id", "name"))

    def test_rejects_short_row(self) -> None:
        with self.assertRaisesRegex(ValueError, "row width 1 does not match"):
            PoolMergeKnot._validate_row_width("Example", (1,), ("id", "name"))


class TestNonKeyValuesChanged(unittest.TestCase):
    def test_identical_non_key_values_are_unchanged(self) -> None:
        existing = (1, "alice")
        row = (1, "alice")
        assert PoolMergeKnot._non_key_values_changed(existing, row, non_key_indices=(1,)) is False

    def test_differing_non_key_values_are_changed(self) -> None:
        existing = (1, "alice")
        row = (1, "alice-2")
        assert PoolMergeKnot._non_key_values_changed(existing, row, non_key_indices=(1,)) is True
