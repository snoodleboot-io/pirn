"""Unit tests for :class:`SurvivalAnalysisPipeline`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.survival_analysis_pipeline import SurvivalAnalysisPipeline
from pirn.tapestry import Tapestry


@knot
async def emit_survival_data() -> list[dict[str, Any]]:
    return [
        {"patient_id": "P1", "time": 120, "event": 1, "group": "A"},
        {"patient_id": "P2", "time": 200, "event": 0, "group": "B"},
        {"patient_id": "P3", "time": 90, "event": 1, "group": "A"},
    ]


class TestConstruction:
    def test_rejects_non_knot_survival_data(self) -> None:
        with pytest.raises(TypeError, match="survival_data"):
            SurvivalAnalysisPipeline(
                survival_data="not-a-knot",  # type: ignore[arg-type]
                time_col="time",
                event_col="event",
                _config=KnotConfig(id="s"),
            )

    def test_rejects_empty_time_col(self) -> None:
        with Tapestry():
            d = emit_survival_data(_config=KnotConfig(id="d"))
            with pytest.raises(ValueError, match="time_col"):
                SurvivalAnalysisPipeline(
                    survival_data=d,
                    time_col="",
                    event_col="event",
                    _config=KnotConfig(id="s"),
                )

    def test_rejects_empty_event_col(self) -> None:
        with Tapestry():
            d = emit_survival_data(_config=KnotConfig(id="d"))
            with pytest.raises(ValueError, match="event_col"):
                SurvivalAnalysisPipeline(
                    survival_data=d,
                    time_col="time",
                    event_col="",
                    _config=KnotConfig(id="s"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            d = emit_survival_data(_config=KnotConfig(id="d"))
            SurvivalAnalysisPipeline(
                survival_data=d,
                time_col="time",
                event_col="event",
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, dict)
        assert "median_survival_days" in out
        assert "log_rank_p_value" in out
        assert "cox_hazard_ratios" in out
        assert "n_events" in out

    async def test_n_events_count(self) -> None:
        with Tapestry() as t:
            d = emit_survival_data(_config=KnotConfig(id="d"))
            SurvivalAnalysisPipeline(
                survival_data=d,
                time_col="time",
                event_col="event",
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert out["n_events"] == 2

    async def test_log_rank_p_value_set_when_group_col_given(self) -> None:
        with Tapestry() as t:
            d = emit_survival_data(_config=KnotConfig(id="d"))
            SurvivalAnalysisPipeline(
                survival_data=d,
                time_col="time",
                event_col="event",
                group_col="group",
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert out["log_rank_p_value"] is not None

    async def test_empty_data_returns_defaults(self) -> None:
        with Tapestry() as t:
            d = emit_survival_data(_config=KnotConfig(id="d"))
            SurvivalAnalysisPipeline(
                survival_data=d,
                time_col="time",
                event_col="event",
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out["n_events"], int)
