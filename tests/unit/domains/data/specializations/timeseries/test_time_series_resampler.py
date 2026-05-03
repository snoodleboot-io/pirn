"""Tests for :class:`TimeSeriesResampler`."""

from __future__ import annotations

from datetime import datetime

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.timeseries.time_series_resampler import (
    TimeSeriesResampler,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = TimeSeriesResampler(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="resampler"),
        )
    return knot


class TestConstruction:
    def test_rejects_non_positive_frequency(self) -> None:
        with pytest.raises(ValueError, match="frequency_seconds"):
            _make(timestamp_column="ts", value_column="v", frequency_seconds=0)

    def test_rejects_invalid_aggregation(self) -> None:
        with pytest.raises(ValueError, match="aggregation"):
            _make(timestamp_column="ts", value_column="v", frequency_seconds=60, aggregation="median")

    def test_rejects_invalid_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(timestamp_column="bad col", value_column="v", frequency_seconds=60)


@pytest.mark.asyncio
class TestBehaviour:
    async def test_buckets_by_frequency(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
            {"ts": datetime(2024, 1, 1, 0, 1, 0), "v": 30},
        ]
        knot = _make(timestamp_column="ts", value_column="v", frequency_seconds=60)
        result = await knot.process(rows=rows)
        assert len(result) == 2

    async def test_mean_aggregation(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]
        knot = _make(timestamp_column="ts", value_column="v", frequency_seconds=60, aggregation="mean")
        result = await knot.process(rows=rows)
        assert result[0]["v"] == 15.0

    async def test_sum_aggregation(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]
        knot = _make(timestamp_column="ts", value_column="v", frequency_seconds=60, aggregation="sum")
        result = await knot.process(rows=rows)
        assert result[0]["v"] == 30

    async def test_last_aggregation(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]
        knot = _make(timestamp_column="ts", value_column="v", frequency_seconds=60, aggregation="last")
        result = await knot.process(rows=rows)
        assert result[0]["v"] == 20

    async def test_first_aggregation(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]
        knot = _make(timestamp_column="ts", value_column="v", frequency_seconds=60, aggregation="first")
        result = await knot.process(rows=rows)
        assert result[0]["v"] == 10

    async def test_result_sorted_ascending(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 2, 0), "v": 5},
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 1},
        ]
        knot = _make(timestamp_column="ts", value_column="v", frequency_seconds=60)
        result = await knot.process(rows=rows)
        assert result[0]["ts"] < result[1]["ts"]

    async def test_empty_input(self) -> None:
        knot = _make(timestamp_column="ts", value_column="v", frequency_seconds=60)
        result = await knot.process(rows=[])
        assert result == []
