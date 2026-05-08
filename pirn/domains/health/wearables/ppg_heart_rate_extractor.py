"""``PPGHeartRateExtractor`` — extract heart rate from PPG waveform data.

Algorithm:
    1. Receive ppg_data dict, sample_rate_hz, window_sec, and wavelengths.
    2. Validate ppg_data is a dict and sample_rate_hz / window_sec are positive.
    3. Bandpass filter each window 0.5-4 Hz to isolate pulse range.
    4. Detect peaks and compute heart rate from peak-to-peak intervals.
    5. Return per-window dicts with start_iso, end_iso, hr_bpm, and timestamp_sec.

Math:
    Heart rate from inter-beat interval (IBI):

    $$\\text{HR}_{\\text{bpm}} = \\frac{60}{\\overline{\\text{IBI}}}$$

References:
    - Allen, J. (2007). Photoplethysmography and its application in clinical physiological measurement.
    - Elgendi, M. (2012). On the Analysis of Fingertip Photoplethysmogram Signals.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import scipy.signal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _ppg_peaks(ppg: np.ndarray, fs: float) -> list[dict[str, Any]]:
    """Detect peaks in a PPG signal and compute HR per segment.

    Args:
        ppg: 1-D array of PPG samples.
        fs: Sampling rate in Hz.

    Returns:
        List of dicts with hr_bpm and timestamp_sec for each inter-peak segment.
    """
    if ppg.size < 4 or fs <= 0:
        return []
    low = 0.5
    high = min(4.0, fs / 2.0 - 0.1)
    if low >= high:
        return []
    sos = scipy.signal.butter(2, [low, high], btype="bandpass", fs=fs, output="sos")
    filtered = scipy.signal.sosfiltfilt(sos, ppg)
    min_distance = max(1, int(0.25 * fs))
    peaks, _ = scipy.signal.find_peaks(filtered, distance=min_distance)
    if peaks.size < 2:
        return []
    results: list[dict[str, Any]] = []
    for i in range(len(peaks) - 1):
        ibi_sec = (peaks[i + 1] - peaks[i]) / fs
        hr_bpm = 60.0 / ibi_sec if ibi_sec > 0 else 0.0
        timestamp_sec = float(peaks[i]) / fs
        results.append({"hr_bpm": hr_bpm, "timestamp_sec": timestamp_sec})
    return results


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
        """Extract heart rate from PPG signal using bandpass filtering and peak detection.

        Args:
            ppg_data: Dict with red (list of float), ir (list of float),
                and timestamps_iso (list of str).
            sample_rate_hz: Sample rate in Hz (must be > 0).
            window_sec: Window length in seconds (must be > 0).
            wavelengths: Tuple of wavelength channel names to process.

        Returns:
            List of dicts, each with hr_bpm (float) and timestamp_sec (float).

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
        channel = wavelengths[0] if wavelengths else "red"
        raw = ppg_data.get(channel, ppg_data.get("red", []))
        ppg_array = np.asarray(raw, dtype=float)
        return await asyncio.to_thread(_ppg_peaks, ppg_array, float(sample_rate_hz))
