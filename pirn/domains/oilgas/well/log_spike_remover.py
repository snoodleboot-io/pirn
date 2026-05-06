"""``LogSpikeRemover`` — remove spikes from well log curves using median absolute deviation.

Algorithm:
    1. Receive a log curve list, an odd ``window_size`` > 1, and a positive
       ``mad_threshold``.
    2. Validate both parameters.
    3. Compute a rolling median and MAD (median absolute deviation) over the
       window.
    4. Replace samples where ``|value - median| / MAD > mad_threshold`` with
       the local median.
    5. Return the despiked log curve with a ``spike_removed`` flag per sample.

Math:
    Median absolute deviation:

    $$\\text{MAD} = \\text{median}\\bigl(|x_i - \\tilde{x}|\\bigr)$$

    Spike detection criterion:

    $$|x_i - \\tilde{x}| / \\text{MAD} > \\tau_{mad}$$

References:
    - Leys, C. et al. (2013). Detecting outliers: do not use standard
      deviation around the mean, use absolute deviation around the median.
      *Journal of Experimental Social Psychology*, 49(4), 764–766.
    - Rider, M.H. & Kennedy, M. (2011). *The Geological Interpretation of
      Well Logs*, 3rd ed. Rider-French Consulting, Chapter 2 (log quality
      control).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class LogSpikeRemover(Knot):
    """Detect and replace spikes in well log data using a rolling MAD filter."""

    def __init__(
        self,
        *,
        log_curve: Knot,
        window_size: Knot | int,
        mad_threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            log_curve=log_curve,
            window_size=window_size,
            mad_threshold=mad_threshold,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
        return sorted_vals[mid]

    async def process(
        self,
        log_curve: list[dict[str, Any]],
        window_size: int,
        mad_threshold: float,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Remove spikes from the log curve using a rolling MAD filter.

        Args:
            log_curve: List of dicts with ``depth_ft`` and ``value``.
            window_size: Odd integer > 1 defining the rolling window size.
            mad_threshold: Positive MAD threshold for spike classification.

        Returns:
            List of dicts with ``depth_ft``, ``value``, and ``spike_removed`` (bool).
        """
        if not isinstance(window_size, int):
            raise TypeError("LogSpikeRemover: window_size must be an int")
        if window_size <= 1 or window_size % 2 == 0:
            raise ValueError(
                "LogSpikeRemover: window_size must be an odd integer greater than 1"
            )
        if not isinstance(mad_threshold, (int, float)):
            raise TypeError("LogSpikeRemover: mad_threshold must be numeric")
        if mad_threshold <= 0:
            raise ValueError("LogSpikeRemover: mad_threshold must be positive")
        half = window_size // 2
        values = [float(e.get("value", 0.0)) for e in log_curve]
        results: list[dict[str, Any]] = []
        for i, entry in enumerate(log_curve):
            lo = max(0, i - half)
            hi = min(len(values), i + half + 1)
            window = values[lo:hi]
            med = self._median(window)
            mad = self._median([abs(v - med) for v in window]) or 1.0
            is_spike = abs(values[i] - med) / mad > float(mad_threshold)
            out_value = med if is_spike else values[i]
            results.append(
                {**entry, "value": out_value, "spike_removed": is_spike}
            )
        return results
