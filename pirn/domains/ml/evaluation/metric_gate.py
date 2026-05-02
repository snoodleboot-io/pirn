"""``MetricGate`` — gate downstream knots by a metric threshold."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.eval_report import EvalReport


class MetricGate(Knot):
    """Return ``True`` iff ``report.metrics[metric] >= min_value``."""

    def __init__(
        self,
        *,
        report: Knot,
        metric: str,
        min_value: float,
        raise_on_fail: bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(metric, str) or not metric:
            raise ValueError("MetricGate: metric must be a non-empty string")
        if not isinstance(min_value, (int, float)):
            raise TypeError("MetricGate: min_value must be numeric")
        if not isinstance(raise_on_fail, bool):
            raise TypeError("MetricGate: raise_on_fail must be a bool")
        self._metric = metric
        self._min_value = float(min_value)
        self._raise_on_fail = raise_on_fail
        super().__init__(report=report, _config=_config, **kwargs)

    async def process(self, report: EvalReport, **_: Any) -> bool:
        if self._metric not in report.metrics:
            raise KeyError(
                f"MetricGate: report has no metric named {self._metric!r}; "
                f"available metrics: {sorted(report.metrics)}"
            )
        observed = float(report.metrics[self._metric])
        passed = observed >= self._min_value
        if not passed and self._raise_on_fail:
            raise ValueError(
                f"MetricGate: metric {self._metric!r} value "
                f"{observed!r} is below threshold {self._min_value!r}"
            )
        return passed
