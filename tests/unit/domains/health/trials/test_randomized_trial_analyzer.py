"""Unit tests for :class:`RandomizedTrialAnalyzer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.randomized_trial_analyzer import RandomizedTrialAnalyzer
from pirn.tapestry import Tapestry


@knot
async def emit_trial_data() -> list[dict[str, Any]]:
    return [
        {"patient_id": "P1", "treatment": True, "outcome": True},
        {"patient_id": "P2", "treatment": True, "outcome": False},
        {"patient_id": "P3", "treatment": False, "outcome": False},
        {"patient_id": "P4", "treatment": False, "outcome": True},
    ]


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_trial_data(self) -> None:
        with self.assertRaisesRegex(TypeError, "trial_data"):
            RandomizedTrialAnalyzer(
                trial_data="not-a-knot",  # type: ignore[arg-type]
                treatment_col="treatment",
                outcome_col="outcome",
                analysis_type="itt",
                _config=KnotConfig(id="a"),
            )

    def test_rejects_empty_treatment_col(self) -> None:
        with Tapestry():
            d = emit_trial_data(_config=KnotConfig(id="d"))
            with self.assertRaisesRegex(ValueError, "treatment_col"):
                RandomizedTrialAnalyzer(
                    trial_data=d,
                    treatment_col="",
                    outcome_col="outcome",
                    analysis_type="itt",
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_empty_outcome_col(self) -> None:
        with Tapestry():
            d = emit_trial_data(_config=KnotConfig(id="d"))
            with self.assertRaisesRegex(ValueError, "outcome_col"):
                RandomizedTrialAnalyzer(
                    trial_data=d,
                    treatment_col="treatment",
                    outcome_col="",
                    analysis_type="itt",
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_invalid_analysis_type(self) -> None:
        with Tapestry():
            d = emit_trial_data(_config=KnotConfig(id="d"))
            with self.assertRaisesRegex(ValueError, "analysis_type"):
                RandomizedTrialAnalyzer(
                    trial_data=d,
                    treatment_col="treatment",
                    outcome_col="outcome",
                    analysis_type="invalid",
                    _config=KnotConfig(id="a"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_itt_returns_expected_keys(self) -> None:
        with Tapestry() as t:
            d = emit_trial_data(_config=KnotConfig(id="d"))
            RandomizedTrialAnalyzer(
                trial_data=d,
                treatment_col="treatment",
                outcome_col="outcome",
                analysis_type="itt",
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert isinstance(out, dict)
        assert out["itt_results"] is not None
        assert out["per_protocol_results"] is None
        assert out["n_total"] == 4
        assert out["n_treated"] == 2
        assert out["n_control"] == 2

    async def test_both_analysis_type(self) -> None:
        with Tapestry() as t:
            d = emit_trial_data(_config=KnotConfig(id="d"))
            RandomizedTrialAnalyzer(
                trial_data=d,
                treatment_col="treatment",
                outcome_col="outcome",
                analysis_type="both",
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert out["itt_results"] is not None
        assert out["per_protocol_results"] is not None
