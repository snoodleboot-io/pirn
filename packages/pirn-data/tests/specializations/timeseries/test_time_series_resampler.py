"""Tests for :class:`TimeSeriesResampler`."""

from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.timeseries.time_series_resampler import (
    TimeSeriesResampler,
)


def _make_knot(**overrides: Any) -> TimeSeriesResampler:
    defaults: dict[str, Any] = {
        "rows": [],
        "timestamp_column": "ts",
        "value_column": "v",
        "frequency_seconds": 60,
        "aggregation": "mean",
        "_config": KnotConfig(id="resampler"),
    }
    defaults.update(overrides)
    return TimeSeriesResampler(**defaults)


class TestTimeSeriesResampler(unittest.IsolatedAsyncioTestCase):
    async def test_buckets_by_frequency(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
            {"ts": datetime(2024, 1, 1, 0, 1, 0), "v": 30},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = TimeSeriesResampler(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                frequency_seconds=60,
                _config=KnotConfig(id="resampler"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert len(result.outputs[k.config.id]) == 2

    async def test_result_sorted_ascending(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 2, 0), "v": 5},
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 1},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows2"))
            k = TimeSeriesResampler(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                frequency_seconds=60,
                _config=KnotConfig(id="resampler2"),
            )
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out[0]["ts"] < out[1]["ts"]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            TimeSeriesResampler(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                frequency_seconds=60,
                aggregation="sum",
                _config=KnotConfig(id="resampler-wire"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["resampler-wire"][0]["v"] == 30


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> TimeSeriesResampler:
        defaults: dict[str, Any] = {
            "rows": [],
            "timestamp_column": "ts",
            "value_column": "v",
            "frequency_seconds": 60,
        }
        defaults.update(kwargs)
        with Tapestry():
            return TimeSeriesResampler(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: TimeSeriesResampler, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "timestamp_column": "ts",
            "value_column": "v",
            "frequency_seconds": 60,
            "aggregation": "mean",
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_positive_frequency(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "frequency_seconds"):
            await self._call(k, frequency_seconds=0)

    async def test_rejects_invalid_aggregation(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "aggregation"):
            await self._call(k, aggregation="median")

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, timestamp_column="bad col")

    async def test_mean_aggregation(self) -> None:
        k = self._make_knot()
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]
        result = await k.process(
            rows=rows, timestamp_column="ts", value_column="v",
            frequency_seconds=60, aggregation="mean",
        )
        assert result[0]["v"] == 15.0

    async def test_last_aggregation(self) -> None:
        k = self._make_knot()
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]
        result = await k.process(
            rows=rows, timestamp_column="ts", value_column="v",
            frequency_seconds=60, aggregation="last",
        )
        assert result[0]["v"] == 20

    async def test_first_aggregation(self) -> None:
        k = self._make_knot()
        rows = [
            {"ts": datetime(2024, 1, 1, 0, 0, 0), "v": 10},
            {"ts": datetime(2024, 1, 1, 0, 0, 30), "v": 20},
        ]
        result = await k.process(
            rows=rows, timestamp_column="ts", value_column="v",
            frequency_seconds=60, aggregation="first",
        )
        assert result[0]["v"] == 10

    async def test_empty_input_returns_empty(self) -> None:
        k = self._make_knot()
        result = await k.process(
            rows=[], timestamp_column="ts", value_column="v",
            frequency_seconds=60, aggregation="mean",
        )
        assert result == []
