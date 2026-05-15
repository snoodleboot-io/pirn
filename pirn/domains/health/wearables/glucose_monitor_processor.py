"""``GlucoseMonitorProcessor`` — process CGM glucose-time-series rows.

Algorithm:
    1. Receive readings sequence, target_low_mg_dl, and target_high_mg_dl.
    2. Validate readings is a list/tuple of Mapping objects.
    3. Validate target_low_mg_dl < target_high_mg_dl.
    4. Extract glucose values and compute standard CGM stats.
    5. Return a mapping of standard CGM metric names to float values.

Math:
    Time-in-range (TIR):

    $$\\text{TIR} = \\frac{|\\{r : L \\leq g_r \\leq H\\}|}{N} \\times 100$$

    where $L$ is target_low_mg_dl, $H$ is target_high_mg_dl, and $N$ is total readings.

References:
    - Battelino, T., et al. (2019). Clinical Targets for Continuous Glucose Monitoring Data Interpretation.
    - Danne, T., et al. (2017). International Consensus on Use of CGM. Diabetes Care.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _cgm_stats(readings: np.ndarray, low: float, high: float) -> dict[str, float]:
    """Compute standard CGM statistics from a glucose readings array.

    Args:
        readings: 1-D array of glucose values in mg/dL.
        low: Lower bound of target range in mg/dL.
        high: Upper bound of target range in mg/dL.

    Returns:
        Dict with mean_glucose, std_glucose, cv, time_in_range_pct,
        time_below_range_pct, and time_above_range_pct.
    """
    if readings.size == 0:
        return {
            "mean_glucose": 0.0,
            "std_glucose": 0.0,
            "cv": 0.0,
            "time_in_range_pct": 0.0,
            "time_below_range_pct": 0.0,
            "time_above_range_pct": 0.0,
        }
    mean_g = float(np.mean(readings))
    std_g = float(np.std(readings, ddof=1)) if readings.size > 1 else 0.0
    cv = (std_g / mean_g * 100.0) if mean_g > 0 else 0.0
    reading_count = readings.size
    tir = float(np.sum((readings >= low) & (readings <= high)) / reading_count * 100.0)
    tbr = float(np.sum(readings < low) / reading_count * 100.0)
    tar = float(np.sum(readings > high) / reading_count * 100.0)
    return {
        "mean_glucose": mean_g,
        "std_glucose": std_g,
        "cv": cv,
        "time_in_range_pct": tir,
        "time_below_range_pct": tbr,
        "time_above_range_pct": tar,
    }


class GlucoseMonitorProcessor(Knot):
    """Process CGM rows into per-subject glucose metrics."""

    def __init__(
        self,
        *,
        readings: Knot | Sequence[Mapping[str, Any]],
        target_low_mg_dl: Knot | float,
        target_high_mg_dl: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            readings=readings,
            target_low_mg_dl=target_low_mg_dl,
            target_high_mg_dl=target_high_mg_dl,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        readings: Sequence[Mapping[str, Any]],
        target_low_mg_dl: float,
        target_high_mg_dl: float,
        **_: Any,
    ) -> Mapping[str, float]:
        """Compute CGM metrics from the glucose readings.

        Args:
            readings: Sequence of Mapping objects each containing a ``glucose_mg_dl`` key.
            target_low_mg_dl: Lower bound of target glucose range in mg/dL.
            target_high_mg_dl: Upper bound of target glucose range in mg/dL (must be > low).

        Returns:
            Mapping of metric name to float value, including mean_glucose, std_glucose,
            cv, time_in_range_pct, time_below_range_pct, and time_above_range_pct.

        Raises:
            TypeError: If readings is not list/tuple or contains non-Mapping items.
            ValueError: If target_low_mg_dl >= target_high_mg_dl.
        """
        if not isinstance(readings, (list, tuple)):
            raise TypeError("GlucoseMonitorProcessor: readings must be list/tuple")
        for reading in readings:
            if not isinstance(reading, Mapping):
                raise TypeError("GlucoseMonitorProcessor: every reading must be Mapping")
        if not isinstance(target_low_mg_dl, (int, float)):
            raise TypeError("GlucoseMonitorProcessor: target_low_mg_dl must be numeric")
        if not isinstance(target_high_mg_dl, (int, float)):
            raise TypeError("GlucoseMonitorProcessor: target_high_mg_dl must be numeric")
        if float(target_low_mg_dl) >= float(target_high_mg_dl):
            raise ValueError(
                "GlucoseMonitorProcessor: target_low_mg_dl must be < target_high_mg_dl"
            )
        glucose_values = np.asarray(
            [float(r["glucose_mg_dl"]) for r in readings if "glucose_mg_dl" in r],
            dtype=float,
        )
        return await asyncio.to_thread(
            _cgm_stats, glucose_values, float(target_low_mg_dl), float(target_high_mg_dl)
        )
