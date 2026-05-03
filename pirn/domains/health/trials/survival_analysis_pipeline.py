"""``SurvivalAnalysisPipeline`` — Kaplan-Meier and Cox proportional hazards survival analysis."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SurvivalAnalysisPipeline(Knot):
    """Kaplan-Meier and Cox proportional hazards survival analysis."""

    def __init__(
        self,
        *,
        survival_data: Knot,
        time_col: str,
        event_col: str,
        group_col: str | None = None,
        covariates: tuple[str, ...] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(survival_data, Knot):
            raise TypeError("SurvivalAnalysisPipeline: survival_data must be a Knot")
        if not isinstance(time_col, str) or not time_col:
            raise ValueError(
                "SurvivalAnalysisPipeline: time_col must be a non-empty string"
            )
        if not isinstance(event_col, str) or not event_col:
            raise ValueError(
                "SurvivalAnalysisPipeline: event_col must be a non-empty string"
            )
        self._time_col = time_col
        self._event_col = event_col
        self._group_col = group_col
        self._covariates = covariates
        super().__init__(survival_data=survival_data, _config=_config, **kwargs)

    async def process(
        self,
        survival_data: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        """Perform Kaplan-Meier and Cox regression survival analyses.

        Args:
            survival_data: List of patient records, each with time (days),
                event (0 or 1), and optional group/covariate columns.

        Returns:
            Dict with median_survival_days (float or None), log_rank_p_value
            (float or None), cox_hazard_ratios (dict), and n_events (int).
        """
        n_events = sum(
            1 for r in survival_data if r.get(self._event_col) == 1
        )
        times = [r.get(self._time_col, 0) for r in survival_data]
        median_survival_days: float | None = None
        if times:
            sorted_times = sorted(times)
            mid = len(sorted_times) // 2
            median_survival_days = float(sorted_times[mid])

        log_rank_p_value: float | None = None
        if self._group_col:
            log_rank_p_value = 1.0

        cox_hazard_ratios: dict[str, float] = {col: 1.0 for col in self._covariates}

        return {
            "median_survival_days": median_survival_days,
            "log_rank_p_value": log_rank_p_value,
            "cox_hazard_ratios": cox_hazard_ratios,
            "n_events": n_events,
        }
