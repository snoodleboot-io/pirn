"""Unit tests for :class:`PropensityScoreMatcherPipeline`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.propensity_score_matcher_pipeline import (
    PropensityScoreMatcherPipeline,
)
from pirn.tapestry import Tapestry


@knot
async def emit_cohort() -> list[dict[str, Any]]:
    return [
        {"patient_id": "P1", "age": 50, "sex": "M", "treated": True},
        {"patient_id": "P2", "age": 45, "sex": "F", "treated": False},
        {"patient_id": "P3", "age": 55, "sex": "M", "treated": False},
    ]


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_cohort(self) -> None:
        with self.assertRaisesRegex(TypeError, "cohort"):
            PropensityScoreMatcherPipeline(
                cohort="not-a-knot",  # type: ignore[arg-type]
                treatment_col="treated",
                covariates=("age", "sex"),
                matching_ratio=1,
                caliper=0.1,
                _config=KnotConfig(id="p"),
            )

    def test_rejects_empty_treatment_col(self) -> None:
        with Tapestry():
            c = emit_cohort(_config=KnotConfig(id="c"))
            with self.assertRaisesRegex(ValueError, "treatment_col"):
                PropensityScoreMatcherPipeline(
                    cohort=c,
                    treatment_col="",
                    covariates=("age",),
                    matching_ratio=1,
                    caliper=0.1,
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_empty_covariates(self) -> None:
        with Tapestry():
            c = emit_cohort(_config=KnotConfig(id="c"))
            with self.assertRaisesRegex(ValueError, "covariates"):
                PropensityScoreMatcherPipeline(
                    cohort=c,
                    treatment_col="treated",
                    covariates=(),
                    matching_ratio=1,
                    caliper=0.1,
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_matching_ratio_less_than_one(self) -> None:
        with Tapestry():
            c = emit_cohort(_config=KnotConfig(id="c"))
            with self.assertRaisesRegex(ValueError, "matching_ratio"):
                PropensityScoreMatcherPipeline(
                    cohort=c,
                    treatment_col="treated",
                    covariates=("age",),
                    matching_ratio=0,
                    caliper=0.1,
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_non_positive_caliper(self) -> None:
        with Tapestry():
            c = emit_cohort(_config=KnotConfig(id="c"))
            with self.assertRaisesRegex(ValueError, "caliper"):
                PropensityScoreMatcherPipeline(
                    cohort=c,
                    treatment_col="treated",
                    covariates=("age",),
                    matching_ratio=1,
                    caliper=0.0,
                    _config=KnotConfig(id="p"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            c = emit_cohort(_config=KnotConfig(id="c"))
            PropensityScoreMatcherPipeline(
                cohort=c,
                treatment_col="treated",
                covariates=("age", "sex"),
                matching_ratio=1,
                caliper=0.1,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, dict)
        assert "matched_pairs" in out
        assert "n_treated" in out
        assert "n_matched" in out
        assert "smd_stats" in out

    async def test_n_treated_count(self) -> None:
        with Tapestry() as t:
            c = emit_cohort(_config=KnotConfig(id="c"))
            PropensityScoreMatcherPipeline(
                cohort=c,
                treatment_col="treated",
                covariates=("age",),
                matching_ratio=1,
                caliper=0.1,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert out["n_treated"] == 1
