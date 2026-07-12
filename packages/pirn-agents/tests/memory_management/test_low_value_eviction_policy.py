"""Unit tests for :class:`LowValueEvictionPolicy`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_agents.memory_management.low_value_eviction_policy import LowValueEvictionPolicy
from tests.memory_management.conftest import make_record


class TestLowValueEvictionPolicy(unittest.TestCase):
    def test_rejects_non_positive_half_life(self) -> None:
        with self.assertRaises(ValueError):
            LowValueEvictionPolicy(half_life_seconds=0)

    def test_no_capacity_evicts_nothing(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        records = [make_record(id="a", importance=0.1), make_record(id="b", importance=0.9)]
        assert LowValueEvictionPolicy().select(records, now=now) == ()

    def test_evicts_lowest_value_beyond_capacity(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        low = make_record(id="low", importance=0.1, created_at=now)
        mid = make_record(id="mid", importance=0.5, created_at=now)
        high = make_record(id="high", importance=0.9, created_at=now)
        policy = LowValueEvictionPolicy()
        evicted = policy.select([high, low, mid], now=now, capacity=2)
        assert [r.id for r in evicted] == ["low"]

    def test_under_capacity_evicts_nothing(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        records = [make_record(id="a", importance=0.5)]
        assert LowValueEvictionPolicy().select(records, now=now, capacity=5) == ()

    def test_rejects_negative_capacity(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        with self.assertRaises(ValueError):
            LowValueEvictionPolicy().select([make_record(id="a")], now=now, capacity=-1)

    def test_ties_break_by_id_deterministically(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        a = make_record(id="a", importance=0.5, created_at=now)
        b = make_record(id="b", importance=0.5, created_at=now)
        c = make_record(id="c", importance=0.5, created_at=now)
        evicted = LowValueEvictionPolicy().select([c, b, a], now=now, capacity=2)
        assert [r.id for r in evicted] == ["a"]
