"""Tests for :class:`LateArrivingEventHandler`."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.timeseries.late_arriving_event_handler import (
    LateArrivingEventHandler,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _ts(seconds: float) -> datetime:
    return datetime(2024, 1, 1) + timedelta(seconds=seconds)


def _make(**kwargs):
    with Tapestry():
        knot = LateArrivingEventHandler(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="late"),
        )
    return knot


class TestConstruction:
    def test_rejects_non_positive_bucket(self) -> None:
        with pytest.raises(ValueError, match="bucket_seconds"):
            _make(
                timestamp_column="ts",
                value_column="v",
                bucket_seconds=0,
                allowed_lateness_seconds=5,
            )

    def test_rejects_non_positive_lateness(self) -> None:
        with pytest.raises(ValueError, match="allowed_lateness_seconds"):
            _make(
                timestamp_column="ts",
                value_column="v",
                bucket_seconds=60,
                allowed_lateness_seconds=-1,
            )

    def test_rejects_invalid_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(
                timestamp_column="bad col",
                value_column="v",
                bucket_seconds=60,
                allowed_lateness_seconds=5,
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_on_time_events_no_corrections(self) -> None:
        rows = [
            {"ts": _ts(0), "v": 1},
            {"ts": _ts(30), "v": 2},
        ]
        knot = _make(
            timestamp_column="ts",
            value_column="v",
            bucket_seconds=60,
            allowed_lateness_seconds=5,
        )
        result = await knot.process(rows=rows)
        corrections = [r for r in result if r.get("is_correction")]
        assert corrections == []

    async def test_late_event_emits_correction(self) -> None:
        rows = [
            {"ts": _ts(0), "v": 10},
            {"ts": _ts(120), "v": 5},
            {"ts": _ts(10), "v": 3},
        ]
        knot = _make(
            timestamp_column="ts",
            value_column="v",
            bucket_seconds=60,
            allowed_lateness_seconds=30,
        )
        result = await knot.process(rows=rows)
        corrections = [r for r in result if r.get("is_correction")]
        assert len(corrections) >= 1

    async def test_all_events_forwarded(self) -> None:
        rows = [{"ts": _ts(i * 10), "v": i} for i in range(5)]
        knot = _make(
            timestamp_column="ts",
            value_column="v",
            bucket_seconds=60,
            allowed_lateness_seconds=5,
        )
        result = await knot.process(rows=rows)
        forwarded = [r for r in result if not r.get("is_correction")]
        assert len(forwarded) == 5

    async def test_empty_input(self) -> None:
        knot = _make(
            timestamp_column="ts",
            value_column="v",
            bucket_seconds=60,
            allowed_lateness_seconds=5,
        )
        result = await knot.process(rows=[])
        assert result == []
