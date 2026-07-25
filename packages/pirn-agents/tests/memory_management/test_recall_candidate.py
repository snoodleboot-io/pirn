"""Unit tests for :class:`RecallCandidate`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.recall_candidate import RecallCandidate
from tests.memory_management.conftest import make_record


class TestRecallCandidate(unittest.TestCase):
    def test_holds_record_and_relevance(self) -> None:
        record = make_record(id="r1")
        candidate = RecallCandidate(record=record, relevance=0.7)
        assert candidate.record is record
        assert candidate.relevance == 0.7

    def test_rejects_non_record(self) -> None:
        with self.assertRaises(TypeError):
            RecallCandidate(record="bad", relevance=0.1)  # type: ignore[arg-type]

    def test_rejects_bool_relevance(self) -> None:
        with self.assertRaises(TypeError):
            RecallCandidate(record=make_record(id="r1"), relevance=True)  # type: ignore[arg-type]
