"""Tests for :class:`DatePartExtractor`."""

from __future__ import annotations

from datetime import datetime
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.feature_engineering.date_part_extractor import (
    DatePartExtractor,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = DatePartExtractor(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="datepart"),
        )
    return knot


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_parts(self) -> None:
        with self.assertRaisesRegex(ValueError, "parts"):
            _make(column="ts", parts=[])

    def test_rejects_unknown_part(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported parts"):
            _make(column="ts", parts=["year", "nanosecond"])

    def test_rejects_invalid_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            _make(column="bad col", parts=["year"])


class TestBehaviour(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_year_month_day(self) -> None:
        rows = [{"ts": datetime(2024, 6, 15, 10, 30)}]
        knot = _make(column="ts", parts=["year", "month", "day"])
        result = await knot.process(rows=rows)
        assert result[0]["ts_year"] == 2024
        assert result[0]["ts_month"] == 6
        assert result[0]["ts_day"] == 15

    async def test_extracts_hour(self) -> None:
        rows = [{"ts": datetime(2024, 1, 1, 14, 0)}]
        knot = _make(column="ts", parts=["hour"])
        result = await knot.process(rows=rows)
        assert result[0]["ts_hour"] == 14

    async def test_extracts_weekday(self) -> None:
        rows = [{"ts": datetime(2024, 1, 1)}]
        knot = _make(column="ts", parts=["weekday"])
        result = await knot.process(rows=rows)
        assert result[0]["ts_weekday"] == 0

    async def test_extracts_quarter(self) -> None:
        rows = [
            {"ts": datetime(2024, 1, 1)},
            {"ts": datetime(2024, 4, 1)},
            {"ts": datetime(2024, 7, 1)},
            {"ts": datetime(2024, 10, 1)},
        ]
        knot = _make(column="ts", parts=["quarter"])
        result = await knot.process(rows=rows)
        assert [r["ts_quarter"] for r in result] == [1, 2, 3, 4]

    async def test_iso_string_input(self) -> None:
        rows = [{"ts": "2024-03-20T08:00:00"}]
        knot = _make(column="ts", parts=["year", "month"])
        result = await knot.process(rows=rows)
        assert result[0]["ts_year"] == 2024
        assert result[0]["ts_month"] == 3

    async def test_original_column_preserved(self) -> None:
        rows = [{"ts": datetime(2024, 1, 1)}]
        knot = _make(column="ts", parts=["year"])
        result = await knot.process(rows=rows)
        assert "ts" in result[0]

    async def test_empty_input(self) -> None:
        knot = _make(column="ts", parts=["year"])
        result = await knot.process(rows=[])
        assert result == []
