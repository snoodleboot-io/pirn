"""Unit tests for :class:`TtlEvictionPolicy`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pirn_agents.memory_management.ttl_eviction_policy import TtlEvictionPolicy
from tests.memory_management.conftest import make_record


class TestTtlEvictionPolicy(unittest.TestCase):
    def test_rejects_non_positive_ttl(self) -> None:
        with self.assertRaises(ValueError):
            TtlEvictionPolicy(ttl_seconds=0)

    def test_evicts_records_older_than_ttl(self) -> None:
        now = datetime(2026, 6, 1, tzinfo=UTC)
        old = make_record(id="old", created_at=now - timedelta(seconds=7200))
        fresh = make_record(id="fresh", created_at=now - timedelta(seconds=60))
        policy = TtlEvictionPolicy(ttl_seconds=3600)
        evicted = policy.select([old, fresh], now=now)
        assert [r.id for r in evicted] == ["old"]

    def test_keeps_records_at_or_under_ttl(self) -> None:
        now = datetime(2026, 6, 1, tzinfo=UTC)
        record = make_record(id="edge", created_at=now - timedelta(seconds=3600))
        policy = TtlEvictionPolicy(ttl_seconds=3600)
        assert policy.select([record], now=now) == ()

    def test_uses_last_accessed_anchor(self) -> None:
        now = datetime(2026, 6, 1, tzinfo=UTC)
        record = make_record(
            id="r1",
            created_at=now - timedelta(days=30),
            last_accessed=now - timedelta(seconds=10),
        )
        policy = TtlEvictionPolicy(ttl_seconds=3600)
        assert policy.select([record], now=now) == ()

    def test_rejects_non_datetime_now(self) -> None:
        policy = TtlEvictionPolicy(ttl_seconds=10)
        with self.assertRaises(TypeError):
            policy.select([make_record(id="r1")], now="now")  # type: ignore[arg-type]
