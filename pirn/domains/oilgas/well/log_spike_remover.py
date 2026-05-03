"""``LogSpikeRemover`` — remove spikes from well log curves using median absolute deviation."""

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
        window_size: int,
        mad_threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._window_size = window_size
        self._mad_threshold = float(mad_threshold)
        super().__init__(log_curve=log_curve, _config=_config, **kwargs)

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
        self, log_curve: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Remove spikes from the log curve using a rolling MAD filter.

        Args:
            log_curve: List of dicts with ``depth_ft`` and ``value``.

        Returns:
            List of dicts with ``depth_ft``, ``value``, and ``spike_removed`` (bool).
        """
        half = self._window_size // 2
        values = [float(e.get("value", 0.0)) for e in log_curve]
        results: list[dict[str, Any]] = []
        for i, entry in enumerate(log_curve):
            lo = max(0, i - half)
            hi = min(len(values), i + half + 1)
            window = values[lo:hi]
            med = self._median(window)
            mad = self._median([abs(v - med) for v in window]) or 1.0
            is_spike = abs(values[i] - med) / mad > self._mad_threshold
            out_value = med if is_spike else values[i]
            results.append(
                {**entry, "value": out_value, "spike_removed": is_spike}
            )
        return results
