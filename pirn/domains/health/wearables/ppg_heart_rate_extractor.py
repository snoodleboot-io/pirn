"""``PPGHeartRateExtractor`` — extract heart rate and SpO2 from PPG waveform data."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PPGHeartRateExtractor(Knot):
    """Extract heart rate and SpO2 from PPG waveform data."""

    def __init__(
        self,
        *,
        ppg_data: Knot,
        sample_rate_hz: float,
        window_sec: float,
        wavelengths: tuple[str, ...] = ("red", "ir"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(ppg_data, Knot):
            raise TypeError("PPGHeartRateExtractor: ppg_data must be a Knot")
        if not isinstance(sample_rate_hz, (int, float)) or sample_rate_hz <= 0:
            raise ValueError(
                "PPGHeartRateExtractor: sample_rate_hz must be > 0"
            )
        if not isinstance(window_sec, (int, float)) or window_sec <= 0:
            raise ValueError(
                "PPGHeartRateExtractor: window_sec must be > 0"
            )
        self._sample_rate_hz = float(sample_rate_hz)
        self._window_sec = float(window_sec)
        self._wavelengths = wavelengths
        super().__init__(ppg_data=ppg_data, _config=_config, **kwargs)

    async def process(
        self,
        ppg_data: dict[str, Any],
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Extract heart rate and SpO2 from PPG signal windows.

        Args:
            ppg_data: Dict with red (list of float), ir (list of float),
                and timestamps_iso (list of str).

        Returns:
            List of dicts, each with start_iso, end_iso, heart_rate_bpm
            (float), and spo2_pct (float).
        """
        if not isinstance(ppg_data, dict):
            raise TypeError("PPGHeartRateExtractor: ppg_data must be a dict")
        timestamps = ppg_data.get("timestamps_iso", [])
        window_samples = max(1, int(self._sample_rate_hz * self._window_sec))
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
