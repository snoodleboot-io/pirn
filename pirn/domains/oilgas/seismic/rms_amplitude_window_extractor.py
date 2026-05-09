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

import math
from typing import Any

import numpy as np

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
                raise TypeError(f"RMSAmplitudeWindowExtractor: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"RMSAmplitudeWindowExtractor: {label} must be positive")
        if not isinstance(volume, dict):
            raise TypeError("RMSAmplitudeWindowExtractor: volume must be a dict")
        if not isinstance(horizon, dict):
            raise TypeError("RMSAmplitudeWindowExtractor: horizon must be a dict")
        traces: list[dict[str, Any]] = volume.get("traces", [])
        sample_interval_ms: float = float(volume.get("sample_interval_ms", 4.0))
        picks: list[dict[str, Any]] = horizon.get("picks", [])

        trace_index: dict[tuple[int, int], np.ndarray] = {}
        for tr in traces:
            key = (int(tr.get("inline", 0)), int(tr.get("crossline", 0)))
            trace_index[key] = np.asarray(tr.get("samples", []), dtype=np.float64)

        def _rms_at_pick(p: dict[str, Any]) -> float:
            key = (int(p.get("inline", 0)), int(p.get("crossline", 0)))
            arr = trace_index.get(key)
            if arr is None or len(arr) == 0:
                return 0.0
            t_center_ms = float(p.get("time_ms", 0.0))
            i_center = round(t_center_ms / sample_interval_ms)
            i_above = max(0, i_center - math.ceil(window_ms_above / sample_interval_ms))
            i_below = min(len(arr), i_center + math.ceil(window_ms_below / sample_interval_ms) + 1)
            window = arr[i_above:i_below]
            if len(window) == 0:
                return 0.0
            return float(np.sqrt(np.mean(window**2)))

        rms_map = [
            {
                "inline": p.get("inline"),
                "crossline": p.get("crossline"),
                "rms_amplitude": _rms_at_pick(p),
            }
            for p in picks
        ]
        return {
            "rms_map": rms_map,
            "window_ms": float(window_ms_above) + float(window_ms_below),
        }
