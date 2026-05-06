"""Unit tests for :class:`PropensityScoreMatcherPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.trials.propensity_score_matcher_pipeline import (
    PropensityScoreMatcherPipeline,
)
from pirn.tapestry import Tapestry

_COHORT: list[dict[str, Any]] = [
    {"patient_id": "P1", "age": 50, "sex": "M", "treated": True},
    {"patient_id": "P2", "age": 45, "sex": "F", "treated": False},
    {"patient_id": "P3", "age": 55, "sex": "M", "treated": False},
]


def _make_knot(
    treatment_col: str = "treated",
    covariates: tuple[str, ...] = ("age", "sex"),
    matching_ratio: int = 1,
    caliper: float = 0.1,
) -> PropensityScoreMatcherPipeline:
    with Tapestry():
        from pirn.core.parameter import Parameter
        src = Parameter("c", list, default=_COHORT, _config=KnotConfig(id="c"))
        return PropensityScoreMatcherPipeline(
            cohort=src,
            treatment_col=treatment_col,
            covariates=covariates,
            matching_ratio=matching_ratio,
            caliper=caliper,
            _config=KnotConfig(id="p"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_treatment_col(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "treatment_col"):
            await knot.process(
                cohort=_COHORT,
                treatment_col="",
                covariates=("age",),
                matching_ratio=1,
                caliper=0.1,
            )

    async def test_rejects_empty_covariates(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "covariates"):
            await knot.process(
                cohort=_COHORT,
                treatment_col="treated",
                covariates=(),
                matching_ratio=1,
                caliper=0.1,
            )

    async def test_rejects_matching_ratio_less_than_one(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "matching_ratio"):
            await knot.process(
                cohort=_COHORT,
                treatment_col="treated",
                covariates=("age",),
                matching_ratio=0,
                caliper=0.1,
            )

    async def test_rejects_non_positive_caliper(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "caliper"):
            await knot.process(
                cohort=_COHORT,
                treatment_col="treated",
                covariates=("age",),
                matching_ratio=1,
                caliper=0.0,
            )

    async def test_returns_dict_with_required_keys(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            cohort=_COHORT,
            treatment_col="treated",
            covariates=("age", "sex"),
            matching_ratio=1,
            caliper=0.1,
        )
        assert isinstance(out, dict)
        assert "matched_pairs" in out
        assert "n_treated" in out
        assert "n_matched" in out
        assert "smd_stats" in out

    async def test_n_treated_count(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            cohort=_COHORT,
            treatment_col="treated",
            covariates=("age",),
            matching_ratio=1,
            caliper=0.1,
        )
        assert out["n_treated"] == 1
