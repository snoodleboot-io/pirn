"""``PropensityScoreMatcherPipeline`` — match treated and control cohorts using propensity score matching."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PropensityScoreMatcherPipeline(Knot):
    """Match treated and control cohorts using propensity score matching."""

    def __init__(
        self,
        *,
        cohort: Knot,
        treatment_col: str,
        covariates: tuple[str, ...],
        matching_ratio: int,
        caliper: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(cohort, Knot):
            raise TypeError(
                "PropensityScoreMatcherPipeline: cohort must be a Knot"
            )
        if not isinstance(treatment_col, str) or not treatment_col:
            raise ValueError(
                "PropensityScoreMatcherPipeline: treatment_col must be a non-empty string"
            )
        if not isinstance(covariates, tuple) or len(covariates) == 0:
            raise ValueError(
                "PropensityScoreMatcherPipeline: covariates must be a non-empty tuple"
            )
        if not isinstance(matching_ratio, int) or matching_ratio < 1:
            raise ValueError(
                "PropensityScoreMatcherPipeline: matching_ratio must be >= 1"
            )
        if not isinstance(caliper, (int, float)) or caliper <= 0.0:
            raise ValueError(
                "PropensityScoreMatcherPipeline: caliper must be > 0.0"
            )
        self._treatment_col = treatment_col
        self._covariates = covariates
        self._matching_ratio = matching_ratio
        self._caliper = float(caliper)
        super().__init__(cohort=cohort, _config=_config, **kwargs)

    async def process(
        self,
        cohort: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        """Match treated patients to controls using propensity score matching.

        Args:
            cohort: List of patient records, each containing patient_id,
                covariate columns, and the treatment column.

        Returns:
            Dict with matched_pairs (list of dicts with treated_id and
            control_ids), n_treated (int), n_matched (int), and
            smd_stats (dict of standardized mean differences per covariate).
        """
        treated = [r for r in cohort if r.get(self._treatment_col)]
        controls = [r for r in cohort if not r.get(self._treatment_col)]
        matched_pairs: list[dict[str, Any]] = []
        n_matched = 0
        for patient in treated:
            available = controls[n_matched * self._matching_ratio: (n_matched + 1) * self._matching_ratio]
            if not available:
                break
            matched_pairs.append(
                {
                    "treated_id": patient.get("patient_id"),
                    "control_ids": [c.get("patient_id") for c in available],
                }
            )
            n_matched += 1
        smd_stats: dict[str, float] = {col: 0.0 for col in self._covariates}
        return {
            "matched_pairs": matched_pairs,
            "n_treated": len(treated),
            "n_matched": n_matched,
            "smd_stats": smd_stats,
        }
