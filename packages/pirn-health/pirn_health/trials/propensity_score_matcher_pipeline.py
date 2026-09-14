# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``PropensityScoreMatcherPipeline`` — match treated and control cohorts using propensity score matching.

Algorithm:
    1. Validate treatment_col, covariates, matching_ratio, and caliper.
    2. Estimate propensity scores via logistic regression on covariates. If the
       logistic regression fails to fit (e.g. singular covariate matrix), raise
       ``ValueError`` rather than silently matching on a stale/default score.
    3. Greedily match each treated patient to up to matching_ratio controls within caliper.
    4. Compute standardized mean differences (SMD) per covariate.
    5. Return matched pairs and SMD statistics.

Math:
    Propensity score estimated via logistic regression:

    $$e(X) = P(T=1 \\mid X) = \\frac{1}{1 + e^{-X\\beta}}$$

    Caliper constraint on matched pairs:

    $$|e_i - e_j| \\leq \\delta$$

    where $\\delta$ is the caliper width.

    Standardized mean difference:

    $$\\text{SMD} = \\frac{\\bar{X}_T - \\bar{X}_C}{\\sqrt{(s_T^2 + s_C^2)/2}}$$

References:
    - Rosenbaum, P.R., & Rubin, D.B. (1983). The central role of the propensity score. Biometrika.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, SupportsFloat, SupportsIndex

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency


class PropensityScoreMatcherPipeline(Knot):
    """Match treated and control cohorts using propensity score matching."""

    def __init__(
        self,
        *,
        cohort: Knot | list[dict[str, Any]],
        treatment_col: Knot | str,
        covariates: Knot | tuple[str, ...],
        matching_ratio: Knot | int,
        caliper: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            cohort=cohort,
            treatment_col=treatment_col,
            covariates=covariates,
            matching_ratio=matching_ratio,
            caliper=caliper,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        cohort: list[dict[str, Any]],
        treatment_col: str,
        covariates: Sequence[str],
        matching_ratio: int,
        caliper: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Match treated patients to controls using propensity score matching.

        Args:
            cohort: List of patient records, each containing patient_id,
                covariate columns, and the treatment column.
            treatment_col: Non-empty column name indicating treatment assignment.
            covariates: Non-empty sequence of covariate column names.
            matching_ratio: Minimum 1 controls per treated patient.
            caliper: Positive caliper width for propensity score matching.

        Returns:
            Dict with matched_pairs (list of dicts with treated_id and
            control_ids), n_treated (int), n_matched (int), and
            smd_stats (dict of standardized mean differences per covariate).

        Raises:
            ValueError: If treatment_col is empty, covariates is empty,
                matching_ratio < 1, or caliper <= 0; or if the underlying
                logistic regression fails to fit.
            TypeError: If matching_ratio is not int or caliper is not numeric.
        """
        if not isinstance(treatment_col, str) or not treatment_col:
            raise ValueError(
                "PropensityScoreMatcherPipeline: treatment_col must be a non-empty string"
            )
        if not isinstance(covariates, (list, tuple)) or len(covariates) == 0:
            raise ValueError(
                "PropensityScoreMatcherPipeline: covariates must be a non-empty sequence"
            )
        if not isinstance(matching_ratio, int) or matching_ratio < 1:
            raise ValueError("PropensityScoreMatcherPipeline: matching_ratio must be >= 1")
        if not isinstance(caliper, (int, float)) or float(caliper) <= 0.0:
            raise ValueError("PropensityScoreMatcherPipeline: caliper must be > 0.0")
        return await asyncio.to_thread(
            self._run_psm, cohort, treatment_col, covariates, matching_ratio, float(caliper)
        )

    @staticmethod
    def _safe_float(raw_value: object) -> float:
        if isinstance(raw_value, memoryview):
            raw_value = raw_value.tobytes()
        if not isinstance(raw_value, (str, bytes, bytearray, SupportsFloat, SupportsIndex)):
            return 0.0
        try:
            return float(raw_value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _smd(treated_vals: np.ndarray, control_vals: np.ndarray) -> float:
        """Standardized mean difference between two groups.

        The pooled denominator uses sample variances (``ddof=1``), which are
        undefined for a group of fewer than two values; the SMD is then
        undefined too and ``nan`` is returned explicitly rather than letting
        numpy emit ``Degrees of freedom <= 0`` and propagate a ``nan``.
        """
        if treated_vals.size < 2 or control_vals.size < 2:
            return float("nan")
        mean_diff = treated_vals.mean() - control_vals.mean()
        pooled_var = (np.var(treated_vals, ddof=1) + np.var(control_vals, ddof=1)) / 2.0
        if pooled_var == 0.0:
            return 0.0
        return float(mean_diff / np.sqrt(pooled_var))

    @staticmethod
    def _run_psm(
        cohort: list[dict[str, Any]],
        treatment_col: str,
        covariates: Sequence[str],
        matching_ratio: int,
        caliper: float,
    ) -> dict[str, Any]:
        for record_index, record in enumerate(cohort):
            if "patient_id" not in record:
                raise ValueError(
                    f"PropensityScoreMatcherPipeline: cohort[{record_index}] missing required "
                    f"field 'patient_id'; got: {list(record)}"
                )
            if treatment_col not in record:
                raise ValueError(
                    f"PropensityScoreMatcherPipeline: cohort[{record_index}] missing required "
                    f"field '{treatment_col}'; got: {list(record)}"
                )
        treated_idx = [
            cohort_index for cohort_index, record in enumerate(cohort) if record[treatment_col]
        ]
        control_idx = [
            cohort_index for cohort_index, record in enumerate(cohort) if not record[treatment_col]
        ]

        covariate_matrix = np.array(
            [
                [
                    PropensityScoreMatcherPipeline._safe_float(record.get(col, 0))
                    for col in covariates
                ]
                for record in cohort
            ]
        )
        treatment_labels = np.array([1 if record[treatment_col] else 0 for record in cohort])

        ps = np.full(len(cohort), 0.5)
        if len(np.unique(treatment_labels)) > 1:
            linear_model = OptionalDependency.require(
                "sklearn.linear_model", extra="health", package="pirn-health"
            )
            try:
                lr = linear_model.LogisticRegression(max_iter=500, random_state=0)
                lr.fit(covariate_matrix, treatment_labels)
                probabilities: np.ndarray = lr.predict_proba(covariate_matrix)
                ps = probabilities[:, 1]
            except Exception as exc:
                raise ValueError(
                    f"PropensityScoreMatcherPipeline: propensity model failed to fit: {exc}"
                ) from exc

        used_controls: set[int] = set()
        matched_treated_idx: list[int] = []
        matched_pairs: list[dict[str, Any]] = []
        n_matched = 0

        for treated_cohort_index in treated_idx:
            ps_treated = ps[treated_cohort_index]
            candidates = [
                ctrl_cohort_index
                for ctrl_cohort_index in control_idx
                if ctrl_cohort_index not in used_controls
                and abs(ps[ctrl_cohort_index] - ps_treated) <= caliper
            ]
            candidates.sort(key=lambda ctrl_cohort_index: abs(ps[ctrl_cohort_index] - ps_treated))
            chosen = candidates[:matching_ratio]
            if not chosen:
                continue
            matched_pairs.append(
                {
                    "treated_id": cohort[treated_cohort_index]["patient_id"],
                    "control_ids": [
                        cohort[ctrl_cohort_index]["patient_id"] for ctrl_cohort_index in chosen
                    ],
                }
            )
            used_controls.update(chosen)
            matched_treated_idx.append(treated_cohort_index)
            n_matched += 1

        matched_control_idx = list(used_controls)

        smd_stats: dict[str, float] = {}
        for covariate_index, col in enumerate(covariates):
            if matched_treated_idx and matched_control_idx:
                treated_vals = covariate_matrix[matched_treated_idx, covariate_index]
                ctrl_vals = covariate_matrix[matched_control_idx, covariate_index]
                smd_stats[col] = PropensityScoreMatcherPipeline._smd(treated_vals, ctrl_vals)
            else:
                smd_stats[col] = 0.0

        return {
            "matched_pairs": matched_pairs,
            "n_treated": len(treated_idx),
            "n_matched": n_matched,
            "smd_stats": smd_stats,
        }
