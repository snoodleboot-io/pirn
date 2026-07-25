"""``Metric`` — base class for evaluation metrics (name + score)."""

from __future__ import annotations

from typing import Any

from pirn_agents.evaluation.metric_result import MetricResult


class Metric:
    """Interface for a scoring metric: a name plus score(actual, expected)."""

    @property
    def name(self) -> str:
        """The metric's stable identifier."""
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    def score(self, actual: Any, expected: Any = None) -> MetricResult:
        """Score ``actual`` (optionally against ``expected``)."""
        raise NotImplementedError(f"{type(self).__name__} must implement score()")
