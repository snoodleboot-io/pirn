"""``MetricCheck`` — check downstream knots by a metric threshold.

Algorithm:
    1. Receive ``report`` (EvalMetadata), ``metric`` (str), ``min_value`` (float),
       and ``raise_on_fail`` (bool) via process().
    2. Validate metric is a non-empty string, min_value is numeric, raise_on_fail is bool.
    3. Check that the metric key exists in the report's metrics mapping.
    4. Compare the observed value against min_value.
    5. If below threshold and raise_on_fail is True, raise ValueError.
    6. Return the comparison boolean.

Math:
    passed = report.metrics[metric] >= min_value

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload


class MetricCheck(Knot):
    """Return ``True`` iff ``report.metrics[metric] >= min_value``."""

    def __init__(
        self,
        *,
        report: Knot,
        metric: Knot | str,
        min_value: Knot | float,
        raise_on_fail: Knot | bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            report=report,
            metric=metric,
            min_value=min_value,
            raise_on_fail=raise_on_fail,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        report: EvalReportPayload,
        metric: str,
        min_value: float,
        raise_on_fail: bool = False,
        **_: Any,
    ) -> bool:
        """Check that the configured metric in the report meets the minimum threshold and return True if it does.

        Args:
            report: EvalReportPayload whose metrics scores mapping is checked.
            metric: Non-empty metric name to look up in the report.
            min_value: Minimum acceptable value; report metric must be >= this.
            raise_on_fail: When True, raise ValueError if the metric fails the threshold.

        Returns:
            True if the metric value is >= min_value, False otherwise.

        Raises:
            ValueError: If metric is empty, min_value is not numeric, or raise_on_fail is not bool.
            KeyError: If the configured metric name is absent from the report.
            ValueError: If raise_on_fail is True and the metric is below the threshold.
        """
        if not isinstance(metric, str) or not metric:
            raise ValueError("MetricCheck: metric must be a non-empty string")
        if not isinstance(min_value, (int, float)):
            raise TypeError("MetricCheck: min_value must be numeric")
        if not isinstance(raise_on_fail, bool):
            raise TypeError("MetricCheck: raise_on_fail must be a bool")
        scores = report.metrics.scores
        if metric not in scores:
            raise KeyError(
                f"MetricCheck: report has no metric named {metric!r}; "
                f"available metrics: {sorted(scores)}"
            )
        observed = float(scores[metric])
        passed = observed >= float(min_value)
        if not passed and raise_on_fail:
            raise ValueError(
                f"MetricCheck: metric {metric!r} value "
                f"{observed!r} is below threshold {min_value!r}"
            )
        return passed
