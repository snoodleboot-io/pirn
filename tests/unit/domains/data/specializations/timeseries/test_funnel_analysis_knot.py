"""Tests for :class:`FunnelAnalysisKnot`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.timeseries.funnel_analysis_knot import (
    FunnelAnalysisKnot,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = FunnelAnalysisKnot(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="funnel"),
        )
    return knot


class TestConstruction:
    def test_rejects_empty_funnel(self) -> None:
        with pytest.raises(ValueError, match="funnel_steps"):
            _make(user_column="uid", event_column="event", funnel_steps=[])

    def test_rejects_invalid_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(user_column="bad col", event_column="event", funnel_steps=["view"])


@pytest.mark.asyncio
class TestBehaviour:
    async def test_full_conversion(self) -> None:
        rows = [
            {"uid": "u1", "event": "view"},
            {"uid": "u1", "event": "click"},
            {"uid": "u1", "event": "purchase"},
            {"uid": "u2", "event": "view"},
            {"uid": "u2", "event": "click"},
        ]
        knot = _make(
            user_column="uid",
            event_column="event",
            funnel_steps=["view", "click", "purchase"],
        )
        result = await knot.process(rows=rows)
        view_row = next(r for r in result if r["step"] == "view")
        click_row = next(r for r in result if r["step"] == "click")
        purchase_row = next(r for r in result if r["step"] == "purchase")
        assert view_row["users"] == 2
        assert click_row["users"] == 2
        assert purchase_row["users"] == 1
        assert view_row["conversion"] is None
        assert click_row["conversion"] == pytest.approx(1.0)
        assert purchase_row["conversion"] == pytest.approx(0.5)

    async def test_no_user_reaches_step_two(self) -> None:
        rows = [{"uid": "u1", "event": "view"}]
        knot = _make(
            user_column="uid",
            event_column="event",
            funnel_steps=["view", "click"],
        )
        result = await knot.process(rows=rows)
        assert result[1]["users"] == 0

    async def test_step_count(self) -> None:
        knot = _make(
            user_column="uid",
            event_column="event",
            funnel_steps=["a", "b", "c"],
        )
        result = await knot.process(rows=[])
        assert len(result) == 3
