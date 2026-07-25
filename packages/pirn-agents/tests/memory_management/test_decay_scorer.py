"""Unit tests for :class:`DecayScorer`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.decay_scorer import DecayScorer
from tests.memory_management.conftest import make_record


def _make_knot() -> DecayScorer:
    with Tapestry():
        return DecayScorer(
            record=make_record(id="r1"),
            now=datetime(2026, 1, 1, tzinfo=UTC),
            _config=KnotConfig(id="ds"),
        )


class TestDecayScorer(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_record_scores_full_importance(self) -> None:
        knot = _make_knot()
        created = datetime(2026, 1, 1, tzinfo=UTC)
        record = make_record(id="r1", importance=0.7, created_at=created)
        score = await knot.process(record=record, now=created, half_life_seconds=3600.0)
        assert score == 0.7

    async def test_one_half_life_halves_score(self) -> None:
        knot = _make_knot()
        created = datetime(2026, 1, 1, tzinfo=UTC)
        now = created + timedelta(seconds=3600)
        record = make_record(id="r1", importance=0.8, created_at=created)
        score = await knot.process(record=record, now=now, half_life_seconds=3600.0)
        assert abs(score - 0.4) < 1e-9

    async def test_uses_last_accessed_as_anchor(self) -> None:
        knot = _make_knot()
        created = datetime(2026, 1, 1, tzinfo=UTC)
        accessed = datetime(2026, 3, 1, tzinfo=UTC)
        record = make_record(id="r1", importance=0.5, created_at=created, last_accessed=accessed)
        score = await knot.process(record=record, now=accessed, half_life_seconds=3600.0)
        assert score == 0.5

    async def test_rejects_non_record(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(record="bad", now=datetime(2026, 1, 1, tzinfo=UTC))  # type: ignore[arg-type]

    async def test_rejects_non_datetime_now(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(record=make_record(id="r1"), now="now")  # type: ignore[arg-type]
