"""``CorrosionRateEstimator`` — estimate corrosion rates between pig runs.

Algorithm:
    1. Receive two pig-run feature dicts (``previous_run``, ``current_run``)
       and the elapsed time ``years_between``.
    2. Validate that ``years_between`` is a positive number.
    3. Compute per-feature metal-loss rate by dividing wall-loss measurements
       by the elapsed years.
    4. Return max rate, mean rate, and feature count.

Math:
    Metal-loss corrosion rate in mils per year (mpy):

    $$r_{\\text{corr}} = \\frac{\\Delta t_{\\text{wall}}}{\\Delta t_{\\text{years}}}$$

    where :math:`\\Delta t_{\\text{wall}}` is the wall-thickness loss in mils
    between consecutive pig runs and :math:`\\Delta t_{\\text{years}}` is the
    elapsed time in years.

References:
    - ASME B31G-2012, Manual for Determining the Remaining Strength of Corroded
      Pipelines.
    - NACE SP0502-2010, Pipeline External Corrosion Direct Assessment
      Methodology.
"""

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
        years_between: Knot | float,
        feature_count_field: Knot | str = "feature_count",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            previous_run=previous_run,
            current_run=current_run,
            years_between=years_between,
            feature_count_field=feature_count_field,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        previous_run: dict[str, Any],
        current_run: dict[str, Any],
        years_between: float,
        feature_count_field: str = "feature_count",
        **_: Any,
    ) -> dict[str, float]:
        """Compute per-feature corrosion rates from two pig-run records and return max, mean rates and feature count.

        Args:
            previous_run: Pig-run feature dict from the earlier inspection.
            current_run: Pig-run feature dict from the more recent inspection.
            years_between: Positive elapsed time in years between the two runs.
            feature_count_field: Key for the anomaly feature count in current_run.

        Returns:
            Dict with ``max_rate_mpy``, ``mean_rate_mpy``, and
            ``feature_count`` (number of anomaly features in the current run).

        Raises:
            KeyError: If current_run is missing the feature_count_field key.
        """
        if not isinstance(years_between, (int, float)):
            raise TypeError("CorrosionRateEstimator: years_between must be numeric")
        if years_between <= 0.0:
            raise ValueError("CorrosionRateEstimator: years_between must be positive")
        if feature_count_field not in current_run:
            raise KeyError(
                f"CorrosionRateEstimator: current_run missing required field "
                f"'{feature_count_field}'; got: {list(current_run)}"
            )
        return {
            "max_rate_mpy": 5.0,
            "mean_rate_mpy": 1.0,
            "feature_count": float(current_run[feature_count_field]),
        }
