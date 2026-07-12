"""Unit tests for :class:`RecencyTrustConflictPolicy`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_agents.memory_management.recency_trust_conflict_policy import RecencyTrustConflictPolicy
from tests.memory_management.conftest import make_record


class TestRecencyTrustConflictPolicy(unittest.TestCase):
    def test_most_recent_wins(self) -> None:
        policy = RecencyTrustConflictPolicy()
        older = make_record(id="old", timestamp=datetime(2026, 1, 1, tzinfo=UTC))
        newer = make_record(id="new", timestamp=datetime(2026, 6, 1, tzinfo=UTC))
        assert policy.resolve([older, newer]) is newer

    def test_trust_breaks_timestamp_tie(self) -> None:
        policy = RecencyTrustConflictPolicy()
        same = datetime(2026, 1, 1, tzinfo=UTC)
        low = make_record(id="low", timestamp=same, trust_signal=0.2)
        high = make_record(id="high", timestamp=same, trust_signal=0.9)
        assert policy.resolve([low, high]) is high

    def test_importance_breaks_trust_tie(self) -> None:
        policy = RecencyTrustConflictPolicy()
        same = datetime(2026, 1, 1, tzinfo=UTC)
        low = make_record(id="low", timestamp=same, trust_signal=0.5, importance=0.1)
        high = make_record(id="high", timestamp=same, trust_signal=0.5, importance=0.8)
        assert policy.resolve([low, high]) is high

    def test_rejects_empty_group(self) -> None:
        with self.assertRaises(ValueError):
            RecencyTrustConflictPolicy().resolve([])

    def test_rejects_non_record(self) -> None:
        with self.assertRaises(TypeError):
            RecencyTrustConflictPolicy().resolve(["bad"])  # type: ignore[list-item]
