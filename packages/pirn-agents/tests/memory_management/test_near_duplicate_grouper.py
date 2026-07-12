"""Unit tests for :class:`NearDuplicateGrouper`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.near_duplicate_grouper import NearDuplicateGrouper
from tests.memory_management.conftest import make_record


class TestNearDuplicateGrouperValidation(unittest.TestCase):
    def test_rejects_out_of_range_threshold(self) -> None:
        with self.assertRaises(ValueError):
            NearDuplicateGrouper(threshold=0.0)
        with self.assertRaises(ValueError):
            NearDuplicateGrouper(threshold=1.5)

    def test_rejects_non_record(self) -> None:
        grouper = NearDuplicateGrouper()
        with self.assertRaises(TypeError):
            grouper.group(["bad"])  # type: ignore[list-item]


class TestNearDuplicateGrouperGrouping(unittest.TestCase):
    def test_groups_near_duplicates_together(self) -> None:
        grouper = NearDuplicateGrouper(threshold=0.5)
        records = [
            make_record(id="a", content="the cat sat on the mat"),
            make_record(id="b", content="the cat sat on a mat"),
            make_record(id="c", content="quantum physics is hard"),
        ]
        groups = grouper.group(records)
        ids = {tuple(r.id for r in group) for group in groups}
        assert ("a", "b") in ids
        assert ("c",) in ids

    def test_transitive_linking_merges_chain(self) -> None:
        grouper = NearDuplicateGrouper(threshold=0.5)
        records = [
            make_record(id="a", content="alpha beta gamma delta"),
            make_record(id="b", content="beta gamma delta epsilon"),
            make_record(id="c", content="gamma delta epsilon zeta"),
        ]
        groups = grouper.group(records)
        # a~b and b~c link all three even though a and c share less.
        assert len(groups) == 1
        assert [r.id for r in groups[0]] == ["a", "b", "c"]

    def test_distinct_content_stays_separate(self) -> None:
        grouper = NearDuplicateGrouper(threshold=0.6)
        records = [
            make_record(id="a", content="apples and oranges"),
            make_record(id="b", content="rockets to the moon"),
        ]
        groups = grouper.group(records)
        assert len(groups) == 2

    def test_empty_input_returns_empty(self) -> None:
        assert NearDuplicateGrouper().group([]) == []

    def test_groups_ordered_by_earliest_member(self) -> None:
        grouper = NearDuplicateGrouper(threshold=0.6)
        records = [
            make_record(id="a", content="unique first item"),
            make_record(id="b", content="shared shared shared token"),
            make_record(id="c", content="shared shared shared token"),
        ]
        groups = grouper.group(records)
        assert groups[0][0].id == "a"
