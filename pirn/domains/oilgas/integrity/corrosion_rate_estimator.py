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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

# Mils-per-year proxy when wall-loss lists are absent: each new anomaly feature
# is assumed to represent ~0.05 mpy of equivalent metal loss (NACE SP0502 §6).
_feature_to_mpy_proxy = 0.05


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

        return await asyncio.to_thread(
            self._compute,
            previous_run,
            current_run,
            float(years_between),
            feature_count_field,
        )

    @staticmethod
    def _compute(
        previous_run: dict[str, Any],
        current_run: dict[str, Any],
        years: float,
        feature_count_field: str,
    ) -> dict[str, float]:
        feature_count = int(current_run[feature_count_field])

        prev_loss = previous_run.get("wall_loss_in", [])
        curr_loss = current_run.get("wall_loss_in", [])

        if prev_loss and curr_loss:
            prev_arr = np.array(prev_loss, dtype=np.float64)
            curr_arr = np.array(curr_loss, dtype=np.float64)
            # Pad shorter array with zeros to align feature indices
            max_feature_count = max(len(prev_arr), len(curr_arr))
            prev_pad = np.pad(prev_arr, (0, max_feature_count - len(prev_arr)))
            curr_pad = np.pad(curr_arr, (0, max_feature_count - len(curr_arr)))
            loss_delta = np.maximum(curr_pad - prev_pad, 0.0)
            # Wall loss in inches → mpy (mils/year): 1 inch = 1000 mils
            max_rate = float(np.max(loss_delta) * 1000.0 / years)
            mean_rate = float(np.mean(loss_delta) * 1000.0 / years)
        else:
            prev_count = int(previous_run.get(feature_count_field, 0))
            new_features = max(0, feature_count - prev_count)
            max_rate = new_features / years * _feature_to_mpy_proxy
            mean_rate = max_rate * 0.5

        return {
            "max_rate_mpy": float(max_rate),
            "mean_rate_mpy": float(mean_rate),
            "feature_count": float(feature_count),
        }
