"""Tests for :class:`SessionizationKnot`."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.timeseries.sessionization_knot import (
    SessionizationKnot,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _ts(minutes: float) -> datetime:
    return datetime(2024, 1, 1) + timedelta(minutes=minutes)


def _make(**kwargs):
    with Tapestry():
        knot = SessionizationKnot(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="session"),
        )
    return knot


class TestConstruction:
    def test_rejects_non_positive_gap(self) -> None:
        with pytest.raises(ValueError, match="inactivity_minutes"):
            _make(entity_columns=["uid"], timestamp_column="ts", inactivity_minutes=-1)

    def test_rejects_invalid_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(entity_columns=["bad col"], timestamp_column="ts", inactivity_minutes=30)


@pytest.mark.asyncio
class TestBehaviour:
    async def test_single_session(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u1", "ts": _ts(5)},
        ]
        knot = _make(entity_columns=["uid"], timestamp_column="ts", inactivity_minutes=30)
        result = await knot.process(rows=rows)
        assert result[0]["session_id"] == result[1]["session_id"]
        assert result[0]["session_seq"] == 1
        assert result[1]["session_seq"] == 2

    async def test_gap_creates_new_session(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u1", "ts": _ts(60)},
        ]
        knot = _make(entity_columns=["uid"], timestamp_column="ts", inactivity_minutes=30)
        result = await knot.process(rows=rows)
        assert result[0]["session_id"] != result[1]["session_id"]

    async def test_different_users_independent(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u2", "ts": _ts(1)},
        ]
        knot = _make(entity_columns=["uid"], timestamp_column="ts", inactivity_minutes=30)
        result = await knot.process(rows=rows)
        assert result[0]["session_id"] != result[1]["session_id"]

    async def test_session_seq_resets_on_new_session(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u1", "ts": _ts(60)},
        ]
        knot = _make(entity_columns=["uid"], timestamp_column="ts", inactivity_minutes=30)
        result = await knot.process(rows=rows)
        assert result[1]["session_seq"] == 1

    async def test_empty_input(self) -> None:
        knot = _make(entity_columns=["uid"], timestamp_column="ts", inactivity_minutes=30)
        result = await knot.process(rows=[])
        assert result == []
