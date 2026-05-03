"""Tests for :class:`CohortAggregator`."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.timeseries.cohort_aggregator import (
    CohortAggregator,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _ts(day: int) -> datetime:
    return datetime(2024, 1, day)


def _make(**kwargs):
    with Tapestry():
        knot = CohortAggregator(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="cohort"),
        )
    return knot


class TestConstruction:
    def test_rejects_non_positive_period(self) -> None:
        with pytest.raises(ValueError, match="period_days"):
            _make(
                user_column="uid",
                timestamp_column="ts",
                metric_column="revenue",
                period_days=0,
            )

    def test_rejects_invalid_aggregation(self) -> None:
        with pytest.raises(ValueError, match="aggregation"):
            _make(
                user_column="uid",
                timestamp_column="ts",
                metric_column="revenue",
                aggregation="median",
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_same_cohort_same_period(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(1), "revenue": 10},
            {"uid": "u1", "ts": _ts(2), "revenue": 20},
        ]
        knot = _make(
            user_column="uid",
            timestamp_column="ts",
            metric_column="revenue",
            period_days=7,
            aggregation="sum",
        )
        result = await knot.process(rows=rows)
        assert len(result) == 1
        assert result[0]["metric_value"] == 30

    async def test_two_cohorts(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(1), "revenue": 10},
            {"uid": "u2", "ts": _ts(8), "revenue": 20},
        ]
        knot = _make(
            user_column="uid",
            timestamp_column="ts",
            metric_column="revenue",
            period_days=7,
            aggregation="sum",
        )
        result = await knot.process(rows=rows)
        cohorts = {r["cohort"] for r in result}
        assert len(cohorts) == 2

    async def test_count_aggregation(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(1), "events": 1},
            {"uid": "u1", "ts": _ts(2), "events": 1},
        ]
        knot = _make(
            user_column="uid",
            timestamp_column="ts",
            metric_column="events",
            period_days=7,
            aggregation="count",
        )
        result = await knot.process(rows=rows)
        assert result[0]["metric_value"] == 2

    async def test_empty_input(self) -> None:
        knot = _make(
            user_column="uid",
            timestamp_column="ts",
            metric_column="revenue",
        )
        result = await knot.process(rows=[])
        assert result == []
