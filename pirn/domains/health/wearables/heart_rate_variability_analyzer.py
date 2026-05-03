"""``HeartRateVariabilityAnalyzer`` — HRV time / frequency / nonlinear metrics.

Production version uses NeuroKit2 / hrv-analysis. This stub returns a
mapping of canonical HRV metrics with zero values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class HeartRateVariabilityAnalyzer(Knot):
    """Compute HRV metrics from R-R intervals."""

    def __init__(
        self,
        *,
        rr_intervals_ms: Sequence[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(rr_intervals_ms, (list, tuple)):
            raise TypeError(
                "HeartRateVariabilityAnalyzer: rr_intervals_ms must be list/tuple"
            )
        for rr in rr_intervals_ms:
            if not isinstance(rr, (int, float)):
                raise TypeError(
                    "HeartRateVariabilityAnalyzer: every RR must be numeric"
                )
        self._rr_intervals = tuple(float(rr) for rr in rr_intervals_ms)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        """Compute time-domain, frequency-domain, and nonlinear HRV metrics from the R-R intervals.

        Returns:
            Mapping of metric name to float value, including sdnn, rmssd, pnn50,
            lf_power, hf_power, and lf_hf_ratio.
        """
        return {
            "sdnn": 0.0,
            "rmssd": 0.0,
            "pnn50": 0.0,
            "lf_power": 0.0,
            "hf_power": 0.0,
            "lf_hf_ratio": 0.0,
        }
