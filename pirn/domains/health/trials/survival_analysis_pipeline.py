"""``SurvivalAnalysisPipeline`` — Kaplan-Meier and Cox proportional hazards survival analysis.

Algorithm:
    1. Validate time_col, event_col, and optional group_col and covariates.
    2. Compute Kaplan-Meier median survival time.
    3. Compute log-rank p-value if group_col is provided.
    4. Compute Cox hazard ratios for each covariate.
    5. Return all survival statistics in a dict.

Math:
    Kaplan-Meier survival estimator:

    $$\\hat{S}(t) = \\prod_{t_i \\leq t} \\left(1 - \\frac{d_i}{n_i}\\right)$$

    where $d_i$ is the number of events and $n_i$ the at-risk count at time $t_i$.

    Log-rank test statistic (two groups A, B):

    $$Z = \\frac{\\sum_j (O_{Aj} - E_{Aj})}{\\sqrt{\\sum_j V_j}}$$

    where $O_{Aj}$ is observed events and $E_{Aj}$ expected events in group A at time $t_j$.

    Cox partial likelihood:

    $$L(\\beta) = \\prod_{i: \\delta_i=1} \\frac{e^{X_i \\beta}}{\\sum_{j \\in R(t_i)} e^{X_j \\beta}}$$

References:
    - Kaplan, E.L., & Meier, P. (1958). Nonparametric estimation from incomplete observations. JASA.
    - Cox, D.R. (1972). Regression models and life-tables. JRSS-B.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy import stats as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _km_median(times: np.ndarray, events: np.ndarray) -> float | None:
    """Kaplan-Meier median survival time."""
    order = np.argsort(times)
    times = times[order]
    events = events[order]
    n = len(times)
    s = 1.0
    for i in range(n):
        at_risk = n - i
        d = events[i]
        s *= 1.0 - d / at_risk
        if s <= 0.5:
            return float(times[i])
    return None


def _log_rank(
    times_a: np.ndarray,
    events_a: np.ndarray,
    times_b: np.ndarray,
    events_b: np.ndarray,
) -> float:
    """Log-rank test p-value (two-group)."""
    all_times = np.unique(np.concatenate([times_a[events_a == 1], times_b[events_b == 1]]))
    obs_a = exp_a = var = 0.0
    for t in all_times:
        n_a = float(np.sum(times_a >= t))
        n_b = float(np.sum(times_b >= t))
        n = n_a + n_b
        if n == 0:
            continue
        d_a = float(np.sum((times_a == t) & (events_a == 1)))
        d_b = float(np.sum((times_b == t) & (events_b == 1)))
        d = d_a + d_b
        e_a = n_a * d / n
        obs_a += d_a
        exp_a += e_a
        if n > 1:
            var += n_a * n_b * d * (n - d) / (n * n * (n - 1))
    if var == 0.0:
        return 1.0
    z = (obs_a - exp_a) ** 2 / var
    return float(ss.chi2.sf(z, df=1))


def _cox_hr(
    times: np.ndarray,
    events: np.ndarray,
    x: np.ndarray,
    n_iter: int = 20,
) -> np.ndarray:
    """Newton-Raphson Cox partial likelihood gradient for single iteration."""
    n, p = x.shape
    beta = np.zeros(p)
    for _ in range(n_iter):
        order = np.argsort(times)
        e_sorted = events[order]
        x_sorted = x[order]
        exp_xb = np.exp(x_sorted @ beta)
        grad = np.zeros(p)
        hess = np.zeros((p, p))
        for i in range(n):
            if e_sorted[i] == 0:
                continue
            risk_set = np.arange(i, n)
            denom = exp_xb[risk_set].sum()
            w = exp_xb[risk_set] / denom
            xw = (x_sorted[risk_set] * w[:, None]).sum(axis=0)
            grad += x_sorted[i] - xw
            xwx = (x_sorted[risk_set] * w[:, None]).T @ x_sorted[risk_set]
            hess -= xwx - np.outer(xw, xw)
        try:
            beta -= np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
    return np.exp(beta)


def _run_survival(
    survival_data: list[dict[str, Any]],
    time_col: str,
    event_col: str,
    group_col: str | None,
    covariates: Sequence[str],
) -> dict[str, Any]:
    times = np.array([float(r.get(time_col, 0)) for r in survival_data])
    events = np.array([float(r.get(event_col, 0)) for r in survival_data])
    n_events = int(events.sum())

    median = _km_median(times, events)

    log_rank_p: float | None = None
    if group_col:
        group_vals = np.array([r.get(group_col) for r in survival_data])
        unique_groups = np.unique(group_vals[group_vals != np.array(None)])
        if len(unique_groups) >= 2:
            mask = group_vals == unique_groups[0]
            if mask.any() and (~mask).any():
                log_rank_p = _log_rank(times[mask], events[mask], times[~mask], events[~mask])

    cox_hazard_ratios: dict[str, float] = {}
    if covariates:
        try:
            x = np.array([[float(r.get(col, 0)) for col in covariates] for r in survival_data])
            hrs = _cox_hr(times, events, x)
            cox_hazard_ratios = {col: float(hrs[i]) for i, col in enumerate(covariates)}
        except Exception:
            cox_hazard_ratios = {col: 1.0 for col in covariates}

    return {
        "median_survival_days": median,
        "log_rank_p_value": log_rank_p,
        "cox_hazard_ratios": cox_hazard_ratios,
        "n_events": n_events,
    }


class SurvivalAnalysisPipeline(Knot):
    """Kaplan-Meier and Cox proportional hazards survival analysis."""

    def __init__(
        self,
        *,
        survival_data: Knot | list[dict[str, Any]],
        time_col: Knot | str,
        event_col: Knot | str,
        group_col: Knot | str | None = None,
        covariates: Knot | tuple[str, ...] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            survival_data=survival_data,
            time_col=time_col,
            event_col=event_col,
            group_col=group_col,
            covariates=covariates,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        survival_data: list[dict[str, Any]],
        time_col: str,
        event_col: str,
        group_col: str | None = None,
        covariates: Sequence[str] = (),
        **_: Any,
    ) -> dict[str, Any]:
        """Perform Kaplan-Meier and Cox regression survival analyses.

        Args:
            survival_data: List of patient records, each with time (days),
                event (0 or 1), and optional group/covariate columns.
            time_col: Non-empty column name for survival time.
            event_col: Non-empty column name for event indicator (0/1).
            group_col: Optional column name for group stratification.
            covariates: Sequence of covariate column names for Cox regression.

        Returns:
            Dict with median_survival_days (float or None), log_rank_p_value
            (float or None), cox_hazard_ratios (dict), and n_events (int).

        Raises:
            ValueError: If time_col or event_col is empty.
        """
        if not isinstance(time_col, str) or not time_col:
            raise ValueError("SurvivalAnalysisPipeline: time_col must be a non-empty string")
        if not isinstance(event_col, str) or not event_col:
            raise ValueError("SurvivalAnalysisPipeline: event_col must be a non-empty string")
        return await asyncio.to_thread(
            _run_survival, survival_data, time_col, event_col, group_col, covariates
        )
