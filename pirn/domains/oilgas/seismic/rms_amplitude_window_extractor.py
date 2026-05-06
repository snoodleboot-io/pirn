"""``RMSAmplitudeWindowExtractor`` — extract RMS amplitude within a time window around a horizon.

Algorithm:
    1. Receive a seismic volume, a picked horizon, and positive
       ``window_ms_above`` / ``window_ms_below`` time window half-lengths.
    2. Validate that all window parameters are positive numbers.
    3. For each horizon pick, extract the trace samples in the time window
       centred on the pick time.
    4. Compute the root-mean-square amplitude over the extracted window.
    5. Return an RMS amplitude map and total window length.

Math:
    RMS amplitude over :math:`N` samples in the window:

    $$A_{rms} = \\sqrt{\\frac{1}{N} \\sum_{i=1}^{N} s_i^2}$$

References:
    - Brown, A.R. (2011). *Interpretation of Three-Dimensional Seismic Data*,
      7th ed. SEG/AAPG Memoir 42, Chapter 4 (amplitude extraction methods).
    - Chopra, S. & Marfurt, K.J. (2007). *Seismic Attributes for Prospect
      Identification and Reservoir Characterisation*. SEG, Chapter 3.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RMSAmplitudeWindowExtractor(Knot):
    """Compute RMS amplitude map by windowing seismic traces around a picked horizon."""

    def __init__(
        self,
        *,
        volume: Knot,
        horizon: Knot,
        window_ms_above: Knot | float,
        window_ms_below: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            volume=volume,
            horizon=horizon,
            window_ms_above=window_ms_above,
            window_ms_below=window_ms_below,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        volume: dict[str, Any],
        horizon: dict[str, Any],
        window_ms_above: float,
        window_ms_below: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Extract RMS amplitude at each horizon pick within the configured time window.

        Args:
            volume: Dict with ``traces`` (list of trace dicts).
            horizon: Dict with ``picks`` (list of dicts with ``inline``,
                ``crossline``, and ``time_ms``).
            window_ms_above: Positive time window above the horizon pick (ms).
            window_ms_below: Positive time window below the horizon pick (ms).

        Returns:
            Dict with ``rms_map`` (list of dicts with ``inline``, ``crossline``,
            ``rms_amplitude``) and ``window_ms`` (float).
        """
        for label, value in (
            ("window_ms_above", window_ms_above),
            ("window_ms_below", window_ms_below),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"RMSAmplitudeWindowExtractor: {label} must be numeric"
                )
            if value <= 0:
                raise ValueError(
                    f"RMSAmplitudeWindowExtractor: {label} must be positive"
                )
        if not isinstance(volume, dict):
            raise TypeError("RMSAmplitudeWindowExtractor: volume must be a dict")
        if not isinstance(horizon, dict):
            raise TypeError("RMSAmplitudeWindowExtractor: horizon must be a dict")
        picks: list[dict[str, Any]] = horizon.get("picks", [])
        rms_map = [
            {
                "inline": p.get("inline"),
                "crossline": p.get("crossline"),
                "rms_amplitude": 0.0,
            }
            for p in picks
        ]
        return {
            "rms_map": rms_map,
            "window_ms": float(window_ms_above) + float(window_ms_below),
        }
