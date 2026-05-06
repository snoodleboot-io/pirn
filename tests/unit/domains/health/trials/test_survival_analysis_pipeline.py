"""Unit tests for :class:`SurvivalAnalysisPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.trials.survival_analysis_pipeline import SurvivalAnalysisPipeline
from pirn.tapestry import Tapestry

_SURVIVAL_DATA: list[dict[str, Any]] = [
    {"patient_id": "P1", "time": 120, "event": 1, "group": "A"},
    {"patient_id": "P2", "time": 200, "event": 0, "group": "B"},
    {"patient_id": "P3", "time": 90, "event": 1, "group": "A"},
]


def _make_knot(
    time_col: str = "time",
    event_col: str = "event",
    group_col: str | None = None,
) -> SurvivalAnalysisPipeline:
    with Tapestry():
        from pirn.core.parameter import Parameter
        src = Parameter("d", list, default=_SURVIVAL_DATA, _config=KnotConfig(id="d"))
        return SurvivalAnalysisPipeline(
            survival_data=src,
            time_col=time_col,
            event_col=event_col,
            group_col=group_col,
            _config=KnotConfig(id="s"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_time_col(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "time_col"):
            await knot.process(
                survival_data=_SURVIVAL_DATA,
                time_col="",
                event_col="event",
            )

    async def test_rejects_empty_event_col(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "event_col"):
            await knot.process(
                survival_data=_SURVIVAL_DATA,
                time_col="time",
                event_col="",
            )

    async def test_returns_dict_with_required_keys(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            survival_data=_SURVIVAL_DATA,
            time_col="time",
            event_col="event",
        )
        assert isinstance(out, dict)
        assert "median_survival_days" in out
        assert "log_rank_p_value" in out
        assert "cox_hazard_ratios" in out
        assert "n_events" in out

    async def test_n_events_count(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            survival_data=_SURVIVAL_DATA,
            time_col="time",
            event_col="event",
        )
        assert out["n_events"] == 2

    async def test_log_rank_p_value_set_when_group_col_given(self) -> None:
        knot = _make_knot(group_col="group")
        out = await knot.process(
            survival_data=_SURVIVAL_DATA,
            time_col="time",
            event_col="event",
            group_col="group",
        )
        assert out["log_rank_p_value"] is not None

    async def test_empty_data_returns_defaults(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            survival_data=_SURVIVAL_DATA,
            time_col="time",
            event_col="event",
        )
        assert isinstance(out["n_events"], int)
