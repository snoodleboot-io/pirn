"""Tests for :class:`RollingWindowAggregator`."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.timeseries.rolling_window_aggregator import (
    RollingWindowAggregator,
)


def _ts(i: int) -> datetime:
    return datetime(2024, 1, 1) + timedelta(hours=i)


def _make_knot(**overrides: Any) -> RollingWindowAggregator:
    defaults: dict[str, Any] = {
        "rows": [],
        "timestamp_column": "ts",
        "value_column": "v",
        "window_size": 2,
        "statistic": "mean",
        "_config": KnotConfig(id="roller"),
    }
    defaults.update(overrides)
    return RollingWindowAggregator(**defaults)


class TestRollingWindowAggregator(unittest.IsolatedAsyncioTestCase):
    async def test_rolling_mean(self) -> None:
        rows = [{"ts": _ts(i), "v": float(i + 1)} for i in range(4)]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = RollingWindowAggregator(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                window_size=2,
                statistic="mean",
                _config=KnotConfig(id="roller"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out[1]["v_mean"] == pytest.approx(1.5)
        assert out[3]["v_mean"] == pytest.approx(3.5)

    async def test_rolling_sum(self) -> None:
        rows = [{"ts": _ts(i), "v": 1.0} for i in range(3)]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows2"))
            k = RollingWindowAggregator(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                window_size=2,
                statistic="sum",
                _config=KnotConfig(id="roller2"),
            )
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out[0]["v_sum"] == 1.0
        assert out[1]["v_sum"] == 2.0

    async def test_output_column_name(self) -> None:
        rows = [{"ts": _ts(0), "v": 1.0}]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows3"))
            k = RollingWindowAggregator(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                window_size=1,
                statistic="sum",
                _config=KnotConfig(id="roller3"),
            )
        result = await t.run(RunRequest())
        assert "v_sum" in result.outputs[k.config.id][0]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        rows = [{"ts": _ts(i), "v": float(i)} for i in range(3)]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            RollingWindowAggregator(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                window_size=3,
                statistic="min",
                _config=KnotConfig(id="roller-wire"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs["roller-wire"]) == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> RollingWindowAggregator:
        defaults: dict[str, Any] = {
            "rows": [],
            "timestamp_column": "ts",
            "value_column": "v",
            "window_size": 2,
        }
        defaults.update(kwargs)
        with Tapestry():
            return RollingWindowAggregator(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: RollingWindowAggregator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "timestamp_column": "ts",
            "value_column": "v",
            "window_size": 2,
            "statistic": "mean",
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_positive_window(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "window_size"):
            await self._call(k, window_size=0)

    async def test_rejects_invalid_statistic(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "statistic"):
            await self._call(k, statistic="median")

    async def test_rolling_min_max(self) -> None:
        k = self._make_knot()
        rows = [{"ts": _ts(i), "v": float(v)} for i, v in enumerate([3, 1, 4, 1, 5])]
        result = await k.process(
            rows=rows, timestamp_column="ts", value_column="v",
            window_size=3, statistic="min",
        )
        assert result[2]["v_min"] == 1.0

    async def test_rolling_std(self) -> None:
        k = self._make_knot()
        rows = [{"ts": _ts(i), "v": float(v)} for i, v in enumerate([2.0, 4.0])]
        result = await k.process(
            rows=rows, timestamp_column="ts", value_column="v",
            window_size=2, statistic="std",
        )
        assert result[1]["v_std"] == pytest.approx(1.0)

    async def test_empty_input_returns_empty(self) -> None:
        k = self._make_knot()
        result = await k.process(
            rows=[], timestamp_column="ts", value_column="v",
            window_size=3, statistic="mean",
        )
        assert result == []
