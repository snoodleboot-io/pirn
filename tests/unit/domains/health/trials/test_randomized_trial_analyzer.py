"""Unit tests for :class:`RandomizedTrialAnalyzer`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.trials.randomized_trial_analyzer import RandomizedTrialAnalyzer
from pirn.tapestry import Tapestry

_TRIAL_DATA: list[dict[str, Any]] = [
    {"patient_id": "P1", "treatment": True, "outcome": True},
    {"patient_id": "P2", "treatment": True, "outcome": False},
    {"patient_id": "P3", "treatment": False, "outcome": False},
    {"patient_id": "P4", "treatment": False, "outcome": True},
]


def _make_knot(analysis_type: str = "itt") -> RandomizedTrialAnalyzer:
    with Tapestry():
        from pirn.core.parameter import Parameter
        src = Parameter("d", list, default=_TRIAL_DATA, _config=KnotConfig(id="d"))
        return RandomizedTrialAnalyzer(
            trial_data=src,
            treatment_col="treatment",
            outcome_col="outcome",
            analysis_type=analysis_type,
            _config=KnotConfig(id="a"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_treatment_col(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "treatment_col"):
            await knot.process(
                trial_data=_TRIAL_DATA,
                treatment_col="",
                outcome_col="outcome",
                analysis_type="itt",
            )

    async def test_rejects_empty_outcome_col(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "outcome_col"):
            await knot.process(
                trial_data=_TRIAL_DATA,
                treatment_col="treatment",
                outcome_col="",
                analysis_type="itt",
            )

    async def test_rejects_invalid_analysis_type(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "analysis_type"):
            await knot.process(
                trial_data=_TRIAL_DATA,
                treatment_col="treatment",
                outcome_col="outcome",
                analysis_type="invalid",
            )

    async def test_itt_returns_expected_keys(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            trial_data=_TRIAL_DATA,
            treatment_col="treatment",
            outcome_col="outcome",
            analysis_type="itt",
        )
        assert isinstance(out, dict)
        assert out["itt_results"] is not None
        assert out["per_protocol_results"] is None
        assert out["n_total"] == 4
        assert out["n_treated"] == 2
        assert out["n_control"] == 2

    async def test_both_analysis_type(self) -> None:
        knot = _make_knot(analysis_type="both")
        out = await knot.process(
            trial_data=_TRIAL_DATA,
            treatment_col="treatment",
            outcome_col="outcome",
            analysis_type="both",
        )
        assert out["itt_results"] is not None
        assert out["per_protocol_results"] is not None
