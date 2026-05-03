"""``RandomizedTrialAnalyzer`` — perform ITT and per-protocol analyses for a randomized controlled trial."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RandomizedTrialAnalyzer(Knot):
    """Perform ITT and per-protocol analyses for a randomized controlled trial."""

    _VALID_ANALYSIS_TYPES: frozenset[str] = frozenset({"itt", "per_protocol", "both"})

    def __init__(
        self,
        *,
        trial_data: Knot,
        treatment_col: str,
        outcome_col: str,
        analysis_type: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(trial_data, Knot):
            raise TypeError("RandomizedTrialAnalyzer: trial_data must be a Knot")
        if not isinstance(treatment_col, str) or not treatment_col:
            raise ValueError(
                "RandomizedTrialAnalyzer: treatment_col must be a non-empty string"
            )
        if not isinstance(outcome_col, str) or not outcome_col:
            raise ValueError(
                "RandomizedTrialAnalyzer: outcome_col must be a non-empty string"
            )
        if analysis_type not in self._VALID_ANALYSIS_TYPES:
            raise ValueError(
                "RandomizedTrialAnalyzer: analysis_type must be one of 'itt', 'per_protocol', 'both'"
            )
        self._treatment_col = treatment_col
        self._outcome_col = outcome_col
        self._analysis_type = analysis_type
        super().__init__(trial_data=trial_data, _config=_config, **kwargs)

    @staticmethod
    def _compute_analysis(
        records: list[dict[str, Any]],
        treatment_col: str,
        outcome_col: str,
    ) -> dict[str, Any]:
        treated = [r for r in records if r.get(treatment_col)]
        control = [r for r in records if not r.get(treatment_col)]
        n_treated_outcomes = sum(1 for r in treated if r.get(outcome_col))
        n_control_outcomes = sum(1 for r in control if r.get(outcome_col))
        rate_treated = n_treated_outcomes / len(treated) if treated else 0.0
        rate_control = n_control_outcomes / len(control) if control else 0.0
        return {
            "n_treated": len(treated),
            "n_control": len(control),
            "outcome_rate_treated": rate_treated,
            "outcome_rate_control": rate_control,
            "risk_difference": rate_treated - rate_control,
        }

    async def process(
        self,
        trial_data: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        """Perform ITT and/or per-protocol analysis on randomized trial data.

        Args:
            trial_data: List of patient records, each containing treatment
                and outcome columns.

        Returns:
            Dict with itt_results (dict or None), per_protocol_results (dict or None),
            n_total (int), n_treated (int), and n_control (int).
        """
        treated = [r for r in trial_data if r.get(self._treatment_col)]
        control = [r for r in trial_data if not r.get(self._treatment_col)]

        itt_results = None
        per_protocol_results = None

        if self._analysis_type in ("itt", "both"):
            itt_results = self._compute_analysis(
                trial_data, self._treatment_col, self._outcome_col
            )

        if self._analysis_type in ("per_protocol", "both"):
            protocol_adherent = [
                r for r in trial_data if r.get("protocol_adherent", True)
            ]
            per_protocol_results = self._compute_analysis(
                protocol_adherent, self._treatment_col, self._outcome_col
            )

        return {
            "itt_results": itt_results,
            "per_protocol_results": per_protocol_results,
            "n_total": len(trial_data),
            "n_treated": len(treated),
            "n_control": len(control),
        }
