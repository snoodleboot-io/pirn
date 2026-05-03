"""Tests for :class:`RollingWindowAggregator`."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.timeseries.rolling_window_aggregator import (
    RollingWindowAggregator,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _ts(i: int) -> datetime:
    return datetime(2024, 1, 1) + timedelta(hours=i)


def _make(**kwargs):
    with Tapestry():
        knot = RollingWindowAggregator(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="roller"),
        )
    return knot


class TestConstruction:
    def test_rejects_non_positive_window(self) -> None:
        with pytest.raises(ValueError, match="window_size"):
            _make(timestamp_column="ts", value_column="v", window_size=0)

    def test_rejects_invalid_statistic(self) -> None:
        with pytest.raises(ValueError, match="statistic"):
            _make(timestamp_column="ts", value_column="v", window_size=3, statistic="median")


@pytest.mark.asyncio
class TestBehaviour:
    async def test_rolling_mean(self) -> None:
        rows = [{"ts": _ts(i), "v": float(i + 1)} for i in range(4)]
        knot = _make(timestamp_column="ts", value_column="v", window_size=2, statistic="mean")
        result = await knot.process(rows=rows)
        assert result[1]["v_mean"] == pytest.approx(1.5)
        assert result[3]["v_mean"] == pytest.approx(3.5)

    async def test_rolling_sum(self) -> None:
        rows = [{"ts": _ts(i), "v": 1.0} for i in range(3)]
        knot = _make(timestamp_column="ts", value_column="v", window_size=2, statistic="sum")
        result = await knot.process(rows=rows)
        assert result[0]["v_sum"] == 1.0
        assert result[1]["v_sum"] == 2.0
        assert result[2]["v_sum"] == 2.0

    async def test_rolling_min_max(self) -> None:
        rows = [{"ts": _ts(i), "v": float(v)} for i, v in enumerate([3, 1, 4, 1, 5])]
        knot_min = _make(timestamp_column="ts", value_column="v", window_size=3, statistic="min")
        result = await knot_min.process(rows=rows)
        assert result[2]["v_min"] == 1.0

    async def test_rolling_std(self) -> None:
        rows = [{"ts": _ts(i), "v": float(v)} for i, v in enumerate([2.0, 4.0])]
        knot = _make(timestamp_column="ts", value_column="v", window_size=2, statistic="std")
        result = await knot.process(rows=rows)
        assert result[1]["v_std"] == pytest.approx(1.0)

    async def test_output_column_name(self) -> None:
        rows = [{"ts": _ts(0), "v": 1.0}]
        knot = _make(timestamp_column="ts", value_column="v", window_size=1, statistic="sum")
        result = await knot.process(rows=rows)
        assert "v_sum" in result[0]

    async def test_empty_input(self) -> None:
        knot = _make(timestamp_column="ts", value_column="v", window_size=3)
        result = await knot.process(rows=[])
        assert result == []
