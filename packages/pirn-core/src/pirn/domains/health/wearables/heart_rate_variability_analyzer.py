"""``HeartRateVariabilityAnalyzer`` — HRV time-domain metrics from R-R intervals.

Algorithm:
    1. Receive rr_intervals_ms sequence of float values.
    2. Validate rr_intervals_ms is a list/tuple of numeric values.
    3. Compute SDNN, RMSSD, pNN50, and mean_hr_bpm.
    4. Return a mapping of HRV metric names to float values.

Math:
    SDNN (standard deviation of NN intervals):

    $$\\text{SDNN} = \\sqrt{\\frac{1}{N-1} \\sum_{i=1}^{N} (\\text{RR}_i - \\overline{\\text{RR}})^2}$$

References:
    - Task Force of the ESC and NASPE (1996). Heart rate variability: Standards of measurement.
    - NeuroKit2: https://neuropsychology.github.io/NeuroKit/
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _hrv_metrics(rr_ms: np.ndarray) -> dict[str, float]:
    """Compute time-domain HRV metrics from an R-R interval array.

    Args:
        rr_ms: 1-D array of R-R intervals in milliseconds.

    Returns:
        Dict with sdnn, rmssd, pnn50, and mean_hr_bpm.
    """
    if rr_ms.size == 0:
        return {"sdnn": 0.0, "rmssd": 0.0, "pnn50": 0.0, "mean_hr_bpm": 0.0}
    sdnn = float(np.std(rr_ms, ddof=1)) if rr_ms.size > 1 else 0.0
    if rr_ms.size > 1:
        diffs = np.diff(rr_ms)
        rmssd = float(np.sqrt(np.mean(diffs**2)))
        pnn50 = float(np.mean(np.abs(diffs) > 50.0))
    else:
        rmssd = 0.0
        pnn50 = 0.0
    mean_hr_bpm = float(60000.0 / np.mean(rr_ms)) if np.mean(rr_ms) > 0 else 0.0
    return {"sdnn": sdnn, "rmssd": rmssd, "pnn50": pnn50, "mean_hr_bpm": mean_hr_bpm}


class HeartRateVariabilityAnalyzer(Knot):
    """Compute HRV metrics from R-R intervals."""

    def __init__(
        self,
        *,
        rr_intervals_ms: Knot | Sequence[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(rr_intervals_ms=rr_intervals_ms, _config=_config, **kwargs)

    async def process(
        self,
        rr_intervals_ms: Sequence[float],
        **_: Any,
    ) -> Mapping[str, float]:
        """Compute time-domain HRV metrics from the R-R intervals.

        Args:
            rr_intervals_ms: Sequence of R-R interval values in milliseconds.

        Returns:
            Mapping of metric name to float value, including sdnn, rmssd, pnn50,
            and mean_hr_bpm.

        Raises:
            TypeError: If rr_intervals_ms is not list/tuple or contains non-numeric values.
        """
        if not isinstance(rr_intervals_ms, (list, tuple)):
            raise TypeError("HeartRateVariabilityAnalyzer: rr_intervals_ms must be list/tuple")
        for rr in rr_intervals_ms:
            if not isinstance(rr, (int, float)):
                raise TypeError("HeartRateVariabilityAnalyzer: every RR must be numeric")
        rr_array = np.asarray(rr_intervals_ms, dtype=float)
        return await asyncio.to_thread(_hrv_metrics, rr_array)
