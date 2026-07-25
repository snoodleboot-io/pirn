"""``EvalGate`` — fail a build when eval quality regresses below thresholds."""

from __future__ import annotations

from typing import Any

from pirn_agents.evaluation.eval_report import EvalReport
from pirn_agents.evaluation.gate_result import GateResult
from pirn_agents.evaluation.threshold_config import ThresholdConfig


class EvalGate:
    """Compare an :class:`EvalReport` against thresholds (and an optional baseline).

    The CI regression gate: a PR's eval run must meet every configured
    :class:`~pirn_agents.evaluation.metric_threshold.MetricThreshold` floor and,
    when a stored ``baseline`` report is supplied, must not drop below the
    baseline on any gated metric. Any violation yields a failing
    :class:`GateResult` carrying a per-metric diff the CI job can print and use to
    fail the build.
    """

    def __init__(self, *, thresholds: ThresholdConfig) -> None:
        """Store the threshold config the gate enforces.

        Raises:
            TypeError: If ``thresholds`` is not a :class:`ThresholdConfig`.
        """
        if not isinstance(thresholds, ThresholdConfig):
            raise TypeError(
                f"EvalGate: thresholds must be a ThresholdConfig, got {type(thresholds).__name__}"
            )
        self._thresholds = thresholds

    def check(self, report: EvalReport, *, baseline: EvalReport | None = None) -> GateResult:
        """Return a :class:`GateResult` for ``report`` against the thresholds.

        A metric breaches when it is missing from the report (``missing``), falls
        below its configured floor (``threshold``), or — when ``baseline`` is
        given — drops below the baseline value (``regression``).

        Raises:
            TypeError: If ``report`` (or ``baseline``) is not an
                :class:`EvalReport`.
        """
        if not isinstance(report, EvalReport):
            raise TypeError(
                f"EvalGate.check: report must be an EvalReport, got {type(report).__name__}"
            )
        if baseline is not None and not isinstance(baseline, EvalReport):
            raise TypeError(
                f"EvalGate.check: baseline must be an EvalReport or None, "
                f"got {type(baseline).__name__}"
            )
        aggregate = report.aggregate()
        baseline_aggregate = baseline.aggregate() if baseline is not None else {}
        breaches: list[dict[str, Any]] = []
        for threshold in self._thresholds.thresholds:
            actual = aggregate.get(threshold.metric)
            if actual is None:
                breaches.append(
                    {
                        "metric": threshold.metric,
                        "kind": "missing",
                        "actual": None,
                        "limit": threshold.min_score,
                    }
                )
                continue
            if actual < threshold.min_score:
                breaches.append(
                    {
                        "metric": threshold.metric,
                        "kind": "threshold",
                        "actual": actual,
                        "limit": threshold.min_score,
                    }
                )
            base_value = baseline_aggregate.get(threshold.metric)
            if base_value is not None and actual < base_value:
                breaches.append(
                    {
                        "metric": threshold.metric,
                        "kind": "regression",
                        "actual": actual,
                        "limit": base_value,
                    }
                )
        return GateResult(
            passed=len(breaches) == 0,
            breaches=tuple(breaches),
            detail={"aggregate": aggregate, "baseline": baseline_aggregate},
        )
