"""Unit tests for :class:`PropensityScoreMatcherPipeline`."""

from __future__ import annotations

import sys
import unittest

try:
    import sklearn  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

import math
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_health.health_optional_dependency import HealthOptionalDependency
from pirn_health.trials.propensity_score_matcher_pipeline import (
    PropensityScoreMatcherPipeline,
)

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

    async def test_propensity_fit_failure_raises_value_error(self) -> None:
        knot = _make_knot()
        mock_lr_instance = MagicMock()
        mock_lr_instance.fit.side_effect = RuntimeError("singular matrix")
        mock_lr_cls = MagicMock(return_value=mock_lr_instance)
        modules = {"sklearn.linear_model": MagicMock(LogisticRegression=mock_lr_cls)}
        with patch.object(
            HealthOptionalDependency,
            "require",
            side_effect=lambda module, **_: modules[module],
        ):
            with self.assertRaisesRegex(ValueError, "propensity model failed to fit"):
                await knot.process(
                    cohort=_COHORT,
                    treatment_col="treated",
                    covariates=("age", "sex"),
                    matching_ratio=1,
                    caliper=0.1,
                )

    async def test_raises_without_sklearn(self) -> None:
        knot = _make_knot()
        with patch.dict(sys.modules, {"sklearn.linear_model": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-health\[health\]"):
                await knot.process(
                    cohort=_COHORT,
                    treatment_col="treated",
                    covariates=("age",),
                    matching_ratio=1,
                    caliper=0.1,
                )


class TestSmd(unittest.TestCase):
    def test_single_value_group_is_undefined_nan(self) -> None:
        smd = PropensityScoreMatcherPipeline._smd(np.array([50.0]), np.array([45.0, 55.0]))
        assert math.isnan(smd)

    def test_zero_pooled_variance_is_zero(self) -> None:
        smd = PropensityScoreMatcherPipeline._smd(np.array([1.0, 1.0]), np.array([1.0, 1.0]))
        assert smd == 0.0

    def test_pooled_standardized_difference(self) -> None:
        smd = PropensityScoreMatcherPipeline._smd(np.array([2.0, 4.0]), np.array([1.0, 3.0]))
        assert smd == 1.0 / math.sqrt(2.0)


class TestRunPsmMatchedTreated(unittest.TestCase):
    def test_smd_uses_the_treated_rows_that_actually_matched(self) -> None:
        cohort: list[dict[str, Any]] = [
            {"patient_id": "T1", "x": 0.0, "treated": True},
            {"patient_id": "T2", "x": 10.0, "treated": True},
            {"patient_id": "T3", "x": 12.0, "treated": True},
            {"patient_id": "C1", "x": 10.0, "treated": False},
            {"patient_id": "C2", "x": 12.0, "treated": False},
        ]
        ps = np.array([0.0, 0.5, 0.6, 0.5, 0.6])
        model = MagicMock()
        model.predict_proba.return_value = np.column_stack([1.0 - ps, ps])
        modules = {
            "sklearn.linear_model": MagicMock(LogisticRegression=MagicMock(return_value=model))
        }
        with patch.object(
            HealthOptionalDependency,
            "require",
            side_effect=lambda module, **_: modules[module],
        ):
            out = PropensityScoreMatcherPipeline._run_psm(cohort, "treated", ("x",), 1, 0.05)
        assert [pair["treated_id"] for pair in out["matched_pairs"]] == ["T2", "T3"]
        # Matched treated rows (10, 12) equal the matched controls (10, 12): SMD 0.
        assert out["smd_stats"]["x"] == 0.0


class TestSafeFloat(unittest.TestCase):
    def test_converts_numeric_and_numeric_string(self) -> None:
        assert PropensityScoreMatcherPipeline._safe_float(3) == 3.0
        assert PropensityScoreMatcherPipeline._safe_float("2.5") == 2.5

    def test_unparseable_string_is_zero(self) -> None:
        assert PropensityScoreMatcherPipeline._safe_float("M") == 0.0

    def test_non_convertible_object_is_zero(self) -> None:
        assert PropensityScoreMatcherPipeline._safe_float(None) == 0.0
        assert PropensityScoreMatcherPipeline._safe_float(object()) == 0.0
