"""``ECGRPeakDetector`` — detect R-peaks in an ECG signal using Pan-Tompkins.

Algorithm:
    1. Receive signal (HealthSignalPayload) and method string.
    2. Validate signal is a HealthSignalPayload and method is one of pan_tompkins/neurokit/elgendi.
    3. Bandpass filter 5-15 Hz to isolate QRS complex frequency band.
    4. Differentiate, square, and integrate with a moving window.
    5. Threshold at 0.6 * max integrated signal and find peaks.
    6. Return a tuple of sample indices corresponding to R-peak positions.

Math:
    Pan-Tompkins signal transformation pipeline:

    y[n] = (x[n] - x[n-2]) / 8  (derivative)
    z[n] = y[n]^2                (squaring)
    m[n] = (1/N) * sum_{k=0}^{N-1} z[n-k]  (moving-window integration, N = 0.150 * fs)

    R-peak threshold: tau = 0.6 * max(m)

References:
    - Pan, J. & Tompkins, W.J. (1985). A real-time QRS detection algorithm.
    - NeuroKit2: https://neuropsychology.github.io/NeuroKit/
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import scipy.signal
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.health_signal_payload import HealthSignalPayload


def _pan_tompkins(ecg: np.ndarray, fs: float) -> tuple[int, ...]:
    """Run Pan-Tompkins R-peak detection on a 1-D ECG array.

    Args:
        ecg: 1-D array of ECG samples.
        fs: Sampling rate in Hz.

    Returns:
        Tuple of integer sample indices for detected R-peaks.
    """
    sos = scipy.signal.butter(2, [5.0, 15.0], btype="bandpass", fs=fs, output="sos")
    filtered = scipy.signal.sosfiltfilt(sos, ecg)
    deriv = np.diff(filtered, prepend=filtered[0])
    squared = deriv**2
    window_samples = max(1, int(0.150 * fs))
    kernel = np.ones(window_samples) / window_samples
    integrated = np.convolve(squared, kernel, mode="same")
    threshold = 0.6 * float(integrated.max()) if integrated.size > 0 else 0.0
    min_distance = max(1, int(0.3 * fs))
    peaks, _ = scipy.signal.find_peaks(integrated, height=threshold, distance=min_distance)
    return tuple(int(p) for p in peaks)


class ECGRPeakDetector(Knot):
    """Detect R-peaks in an ECG signal."""

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, method=method, _config=_config, **kwargs)

    async def process(
        self,
        signal: HealthSignalPayload,
        method: str,
        **_: Any,
    ) -> tuple[int, ...]:
        """Detect R-peak sample indices in the ECG signal using the configured method.

        Args:
            signal: HealthSignalPayload containing the ECG recording.
            method: One of pan_tompkins, neurokit, elgendi.

        Returns:
            Tuple of integer sample indices corresponding to detected R-peaks.

        Raises:
            TypeError: If signal is not a HealthSignalPayload.
            ValueError: If method is not one of the supported options.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("ECGRPeakDetector: signal must be a HealthSignalPayload")
        if method not in ("pan_tompkins", "neurokit", "elgendi"):
            raise ValueError(
                "ECGRPeakDetector: method must be one of pan_tompkins/neurokit/elgendi"
            )
        ecg = signal.data if signal.data.ndim == 1 else signal.data[0]
        fs = signal.frame.sample_rate_hz
        return await asyncio.to_thread(_pan_tompkins, ecg, fs)
