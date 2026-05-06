"""Tests for :class:`LateArrivingEventHandler`."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.timeseries.late_arriving_event_handler import (
    LateArrivingEventHandler,
)
from pirn.tapestry import Tapestry


def _ts(seconds: float) -> datetime:
    return datetime(2024, 1, 1) + timedelta(seconds=seconds)


def _make_knot(**overrides: Any) -> LateArrivingEventHandler:
    defaults: dict[str, Any] = {
        "rows": [],
        "timestamp_column": "ts",
        "value_column": "v",
        "bucket_seconds": 60,
        "allowed_lateness_seconds": 30,
        "_config": KnotConfig(id="late"),
    }
    defaults.update(overrides)
    return LateArrivingEventHandler(**defaults)


class TestLateArrivingEventHandler(unittest.IsolatedAsyncioTestCase):
    async def test_on_time_events_no_corrections(self) -> None:
        rows = [
            {"ts": _ts(0), "v": 1},
            {"ts": _ts(30), "v": 2},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = LateArrivingEventHandler(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                bucket_seconds=60,
                allowed_lateness_seconds=5,
                _config=KnotConfig(id="late"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        corrections = [r for r in out if r.get("is_correction")]
        assert corrections == []

    async def test_late_event_emits_correction(self) -> None:
        rows = [
            {"ts": _ts(0), "v": 10},
            {"ts": _ts(120), "v": 5},
            {"ts": _ts(10), "v": 3},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows2"))
            k = LateArrivingEventHandler(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                bucket_seconds=60,
                allowed_lateness_seconds=30,
                _config=KnotConfig(id="late2"),
            )
        result = await t.run(RunRequest())
        corrections = [r for r in result.outputs[k.config.id] if r.get("is_correction")]
        assert len(corrections) >= 1


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        rows = [{"ts": _ts(i * 10), "v": i} for i in range(5)]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            LateArrivingEventHandler(
                rows=r_knot,
                timestamp_column="ts",
                value_column="v",
                bucket_seconds=60,
                allowed_lateness_seconds=5,
                _config=KnotConfig(id="late-wire"),
            )
        result = await t.run(RunRequest())
        forwarded = [r for r in result.outputs["late-wire"] if not r.get("is_correction")]
        assert len(forwarded) == 5


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> LateArrivingEventHandler:
        defaults: dict[str, Any] = {
            "rows": [],
            "timestamp_column": "ts",
            "value_column": "v",
            "bucket_seconds": 60,
            "allowed_lateness_seconds": 30,
        }
        defaults.update(kwargs)
        with Tapestry():
            return LateArrivingEventHandler(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: LateArrivingEventHandler, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "timestamp_column": "ts",
            "value_column": "v",
            "bucket_seconds": 60,
            "allowed_lateness_seconds": 30,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_positive_bucket(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "bucket_seconds"):
            await self._call(k, bucket_seconds=0)

    async def test_rejects_non_positive_lateness(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "allowed_lateness_seconds"):
            await self._call(k, allowed_lateness_seconds=-1)

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, timestamp_column="bad col")

    async def test_empty_input_returns_empty(self) -> None:
        k = self._make_knot()
        result = await k.process(
            rows=[], timestamp_column="ts", value_column="v",
            bucket_seconds=60, allowed_lateness_seconds=30,
        )
        assert result == []
