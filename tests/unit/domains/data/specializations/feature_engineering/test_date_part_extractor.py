"""Tests for :class:`DatePartExtractor`."""

from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.feature_engineering.date_part_extractor import (
    DatePartExtractor,
)


def _make_knot(**overrides: Any) -> DatePartExtractor:
    defaults: dict[str, Any] = {
        "column": "ts",
        "parts": ("year",),
    }
    defaults.update(overrides)
    return DatePartExtractor(rows=[], **defaults, _config=KnotConfig(id="datepart"))


class TestDatePartExtractor(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_year_month_day(self) -> None:
        rows = [{"ts": datetime(2024, 6, 15, 10, 30)}]
        k = _make_knot(parts=("year", "month", "day"))
        result = await k.process(rows=rows, column="ts", parts=("year", "month", "day"))
        assert result[0]["ts_year"] == 2024
        assert result[0]["ts_month"] == 6
        assert result[0]["ts_day"] == 15

    async def test_extracts_hour(self) -> None:
        rows = [{"ts": datetime(2024, 1, 1, 14, 0)}]
        k = _make_knot(parts=("hour",))
        result = await k.process(rows=rows, column="ts", parts=("hour",))
        assert result[0]["ts_hour"] == 14

    async def test_extracts_weekday(self) -> None:
        rows = [{"ts": datetime(2024, 1, 1)}]
        k = _make_knot(parts=("weekday",))
        result = await k.process(rows=rows, column="ts", parts=("weekday",))
        assert result[0]["ts_weekday"] == 0

    async def test_extracts_quarter(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1)},
            {"ts": datetime(2024, 4, 1)},
            {"ts": datetime(2024, 7, 1)},
            {"ts": datetime(2024, 10, 1)},
        ]
        k = _make_knot(parts=("quarter",))
        result = await k.process(rows=rows, column="ts", parts=("quarter",))
        assert [r["ts_quarter"] for r in result] == [1, 2, 3, 4]

    async def test_iso_string_input(self) -> None:
        rows = [{"ts": "2024-03-20T08:00:00"}]
        k = _make_knot(parts=("year", "month"))
        result = await k.process(rows=rows, column="ts", parts=("year", "month"))
        assert result[0]["ts_year"] == 2024
        assert result[0]["ts_month"] == 3

    async def test_original_column_preserved(self) -> None:
        rows = [{"ts": datetime(2024, 1, 1)}]
        k = _make_knot()
        result = await k.process(rows=rows, column="ts", parts=("year",))
        assert "ts" in result[0]

    async def test_empty_input(self) -> None:
        k = _make_knot()
        result = await k.process(rows=[], column="ts", parts=("year",))
        assert result == []

    async def test_tapestry_run(self) -> None:
        rows = [{"ts": datetime(2024, 6, 15)}]
        with Tapestry() as t:
            DatePartExtractor(
                rows=rows, column="ts", parts=("year",), _config=KnotConfig(id="dp")
            )
        result = await t.run(RunRequest())
        assert result.succeeded


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [{"ts": datetime(2024, 6, 15)}]

        with Tapestry() as t:
            rows_knot = emit_rows(_config=KnotConfig(id="rows"))
            DatePartExtractor(
                rows=rows_knot,
                column="ts",
                parts=("year",),
                _config=KnotConfig(id="dp"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["dp"][0]["ts_year"] == 2024


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> DatePartExtractor:
        defaults: dict[str, Any] = {
            "column": "ts",
            "parts": ("year",),
        }
        defaults.update(kwargs)
        with Tapestry():
            return DatePartExtractor(rows=[], **defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DatePartExtractor, **overrides: Any) -> Any:
        args: dict[str, Any] = {
            "rows": [{"ts": datetime(2024, 1, 1)}],
            "column": "ts",
            "parts": ("year",),
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_empty_parts(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "parts"):
            await self._call(k, parts=())

    async def test_rejects_unknown_part(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "unsupported parts"):
            await self._call(k, parts=("year", "nanosecond"))

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, column="bad col")
