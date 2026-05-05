"""Tests for :class:`FunnelAnalysisKnot`."""

from __future__ import annotations

import unittest
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.timeseries.funnel_analysis_knot import (
    FunnelAnalysisKnot,
)
from pirn.tapestry import Tapestry

_STEPS = ["view", "click", "purchase"]


def _make_knot(**overrides: Any) -> FunnelAnalysisKnot:
    defaults: dict[str, Any] = {
        "rows": [],
        "user_column": "uid",
        "event_column": "event",
        "funnel_steps": _STEPS,
        "_config": KnotConfig(id="funnel"),
    }
    defaults.update(overrides)
    return FunnelAnalysisKnot(**defaults)


class TestFunnelAnalysisKnot(unittest.IsolatedAsyncioTestCase):
    async def test_full_conversion(self) -> None:
        rows = [
            {"uid": "u1", "event": "view"},
            {"uid": "u1", "event": "click"},
            {"uid": "u1", "event": "purchase"},
            {"uid": "u2", "event": "view"},
            {"uid": "u2", "event": "click"},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = FunnelAnalysisKnot(
                rows=r_knot,
                user_column="uid",
                event_column="event",
                funnel_steps=_STEPS,
                _config=KnotConfig(id="funnel"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        view_row = next(r for r in out if r["step"] == "view")
        click_row = next(r for r in out if r["step"] == "click")
        purchase_row = next(r for r in out if r["step"] == "purchase")
        assert view_row["users"] == 2
        assert click_row["users"] == 2
        assert purchase_row["users"] == 1
        assert view_row["conversion"] is None
        assert click_row["conversion"] == pytest.approx(1.0)
        assert purchase_row["conversion"] == pytest.approx(0.5)

    async def test_step_count_matches_funnel_length(self) -> None:
        @knot
        async def emit_rows() -> list:
            return []

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows2"))
            FunnelAnalysisKnot(
                rows=r_knot,
                user_column="uid",
                event_column="event",
                funnel_steps=["a", "b", "c"],
                _config=KnotConfig(id="funnel2"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs["funnel2"]) == 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        rows = [
            {"uid": "u1", "event": "view"},
            {"uid": "u1", "event": "click"},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            FunnelAnalysisKnot(
                rows=r_knot,
                user_column="uid",
                event_column="event",
                funnel_steps=["view", "click"],
                _config=KnotConfig(id="funnel-wire"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["funnel-wire"]
        assert out[0]["users"] == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> FunnelAnalysisKnot:
        defaults: dict[str, Any] = {
            "rows": [],
            "user_column": "uid",
            "event_column": "event",
            "funnel_steps": _STEPS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return FunnelAnalysisKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: FunnelAnalysisKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "user_column": "uid",
            "event_column": "event",
            "funnel_steps": _STEPS,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_empty_funnel(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "funnel_steps"):
            await self._call(k, funnel_steps=[])

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, user_column="bad col")

    async def test_no_user_reaches_step_two(self) -> None:
        k = self._make_knot()
        result = await k.process(
            rows=[{"uid": "u1", "event": "view"}],
            user_column="uid",
            event_column="event",
            funnel_steps=["view", "click"],
        )
        assert result[1]["users"] == 0
