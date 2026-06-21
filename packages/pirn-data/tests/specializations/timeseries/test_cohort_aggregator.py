"""Tests for :class:`CohortAggregator`."""

from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.timeseries.cohort_aggregator import CohortAggregator


def _ts(day: int) -> datetime:
    return datetime(2024, 1, day)


def _make_knot(**overrides: Any) -> CohortAggregator:
    defaults: dict[str, Any] = {
        "user_column": "uid",
        "timestamp_column": "ts",
        "metric_column": "revenue",
        "period_days": 7,
        "aggregation": "sum",
        "_config": KnotConfig(id="cohort"),
    }
    defaults.update(overrides)
    # rows must be provided; use a placeholder list knot or pass directly
    if "rows" not in defaults:
        defaults["rows"] = []
    return CohortAggregator(**defaults)


class TestCohortAggregator(unittest.IsolatedAsyncioTestCase):
    async def test_same_cohort_same_period(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(1), "revenue": 10},
            {"uid": "u1", "ts": _ts(2), "revenue": 20},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = CohortAggregator(
                rows=r_knot,
                user_column="uid",
                timestamp_column="ts",
                metric_column="revenue",
                period_days=7,
                aggregation="sum",
                _config=KnotConfig(id="cohort"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert len(out) == 1
        assert out[0]["metric_value"] == 30

    async def test_two_cohorts(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(1), "revenue": 10},
            {"uid": "u2", "ts": _ts(8), "revenue": 20},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows2"))
            CohortAggregator(
                rows=r_knot,
                user_column="uid",
                timestamp_column="ts",
                metric_column="revenue",
                period_days=7,
                aggregation="sum",
                _config=KnotConfig(id="cohort2"),
            )
        result = await t.run(RunRequest())
        cohorts = {r["cohort"] for r in result.outputs["cohort2"]}
        assert len(cohorts) == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(1), "revenue": 5},
            {"uid": "u1", "ts": _ts(2), "revenue": 5},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            CohortAggregator(
                rows=r_knot,
                user_column="uid",
                timestamp_column="ts",
                metric_column="revenue",
                aggregation="count",
                _config=KnotConfig(id="cohort-wire"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["cohort-wire"][0]["metric_value"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> CohortAggregator:
        defaults: dict[str, Any] = {
            "user_column": "uid",
            "timestamp_column": "ts",
            "metric_column": "revenue",
        }
        defaults.update(kwargs)
        with Tapestry():
            return CohortAggregator(rows=[], **defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: CohortAggregator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "user_column": "uid",
            "timestamp_column": "ts",
            "metric_column": "revenue",
            "period_days": 7,
            "aggregation": "count",
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_positive_period(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "period_days"):
            await self._call(k, period_days=0)

    async def test_rejects_invalid_aggregation(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "aggregation"):
            await self._call(k, aggregation="median")

    async def test_empty_input_returns_empty(self) -> None:
        k = self._make_knot()
        result = await k.process(
            rows=[], user_column="uid", timestamp_column="ts",
            metric_column="revenue", period_days=7, aggregation="count",
        )
        assert result == []
