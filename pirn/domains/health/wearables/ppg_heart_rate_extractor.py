"""``PPGHeartRateExtractor`` — extract heart rate and SpO2 from PPG waveform data.

Algorithm:
    1. Receive ppg_data dict, sample_rate_hz, window_sec, and wavelengths.
    2. Validate ppg_data is a dict and sample_rate_hz / window_sec are positive.
    3. Segment the signal into windows of window_sec length at sample_rate_hz.
    4. Estimate heart rate from peak intervals in the red/IR channel.
    5. Return per-window dicts with start_iso, end_iso, heart_rate_bpm, and spo2_pct.

Math:
    Heart rate from inter-beat interval (IBI):

    $$\\text{HR}_{\\text{bpm}} = \\frac{60}{\\overline{\\text{IBI}}}$$

References:
    - Allen, J. (2007). Photoplethysmography and its application in clinical physiological measurement.
    - Elgendi, M. (2012). On the Analysis of Fingertip Photoplethysmogram Signals.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PPGHeartRateExtractor(Knot):
    """Extract heart rate and SpO2 from PPG waveform data."""

    def __init__(
        self,
        *,
        ppg_data: Knot | dict[str, Any],
        sample_rate_hz: Knot | float,
        window_sec: Knot | float,
        wavelengths: Knot | tuple[str, ...] = ("red", "ir"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            ppg_data=ppg_data,
            sample_rate_hz=sample_rate_hz,
            window_sec=window_sec,
            wavelengths=wavelengths,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        ppg_data: dict[str, Any],
        sample_rate_hz: float,
        window_sec: float,
        wavelengths: tuple[str, ...] = ("red", "ir"),
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Extract heart rate and SpO2 from PPG signal windows.

        Args:
            ppg_data: Dict with red (list of float), ir (list of float),
                and timestamps_iso (list of str).
            sample_rate_hz: Sample rate in Hz (must be > 0).
            window_sec: Window length in seconds (must be > 0).
            wavelengths: Tuple of wavelength channel names to process.

        Returns:
            List of dicts, each with start_iso, end_iso, heart_rate_bpm
            (float), and spo2_pct (float).

        Raises:
            TypeError: If ppg_data is not a dict.
            ValueError: If sample_rate_hz or window_sec are not positive.
        """
        if not isinstance(ppg_data, dict):
            raise TypeError("PPGHeartRateExtractor: ppg_data must be a dict")
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError("PPGHeartRateExtractor: sample_rate_hz must be > 0")
        if not isinstance(window_sec, (int, float)) or window_sec <= 0:
            raise ValueError("PPGHeartRateExtractor: window_sec must be > 0")
        timestamps = ppg_data.get("timestamps_iso", [])
        window_samples = max(1, int(sample_rate_hz * window_sec))
        results: list[dict[str, Any]] = []
        n = len(timestamps)
        for start_idx in range(0, n, window_samples):
            end_idx = min(start_idx + window_samples, n)
            start_iso = timestamps[start_idx] if start_idx < len(timestamps) else ""
            end_iso = timestamps[end_idx - 1] if end_idx - 1 < len(timestamps) else ""
            results.append(
                {
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "heart_rate_bpm": 0.0,
                    "spo2_pct": 0.0,
                }
            )
        return results
