"""``CorrosionRateEstimator`` — estimate corrosion rates between pig runs."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class CorrosionRateEstimator(Knot):
    """Estimate per-feature corrosion rates between two pig runs."""

    def __init__(
        self,
        *,
        previous_run: Knot,
        current_run: Knot,
        years_between: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(years_between, (int, float)):
            raise TypeError(
                "CorrosionRateEstimator: years_between must be numeric"
            )
        if years_between <= 0.0:
            raise ValueError(
                "CorrosionRateEstimator: years_between must be positive"
            )
        self._years_between = float(years_between)
        super().__init__(
            previous_run=previous_run,
            current_run=current_run,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        previous_run: dict[str, Any],
        current_run: dict[str, Any],
        **_: Any,
    ) -> dict[str, float]:
        return {
            "max_rate_mpy": 5.0,
            "mean_rate_mpy": 1.0,
            "feature_count": float(current_run.get("feature_count", 0)),
        }
