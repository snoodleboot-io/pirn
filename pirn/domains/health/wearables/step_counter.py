"""``StepCounter`` — derive step count from accelerometer data.

Algorithm:
    1. Receive signal (SignalPayload) and threshold float.
    2. Validate signal is a SignalPayload and threshold is non-negative.
    3. Compute the acceleration magnitude envelope from the tri-axial signal.
    4. Detect peaks above an adaptive threshold using a windowed peak finder.
    5. Return the total number of detected peaks as the step count.

Math:
    Acceleration magnitude:

    $$a = \\sqrt{a_x^2 + a_y^2 + a_z^2}$$

References:
    - Weinberg, H. (2002). Using the ADXL202 in Pedometer and Personal Navigation Applications.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import scipy.signal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_payload import SignalPayload


def _count_steps(data: np.ndarray, fs: float) -> int:
    """Count steps by detecting peaks in accelerometer magnitude.

    Args:
        data: Array of shape ``(channels, samples)`` or ``(samples,)``.
        fs: Sampling rate in Hz.

    Returns:
        Number of detected steps.
    """
    if data.ndim > 1:
        magnitude = np.sqrt(np.sum(data**2, axis=0))
    else:
        magnitude = data
    if magnitude.size == 0:
        return 0
    threshold = 0.5 * float(np.std(magnitude)) + float(np.mean(magnitude))
    min_distance = max(1, int(0.5 * fs))
    peaks, _ = scipy.signal.find_peaks(magnitude, height=threshold, distance=min_distance)
    return int(peaks.size)


class StepCounter(Knot):
    """Count steps from a tri-axial accelerometer signal."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, threshold=threshold, _config=_config, **kwargs)

    async def process(
        self,
        signal: SignalPayload,
        threshold: float,
        **_: Any,
    ) -> int:
        """Count steps by detecting acceleration peaks above the threshold.

        Args:
            signal: SignalPayload containing the tri-axial accelerometer recording.
            threshold: Minimum peak height threshold (must be >= 0). Unused — adaptive
                threshold is derived from signal statistics.

        Returns:
            Total number of steps detected in the accelerometer signal.

        Raises:
            TypeError: If signal is not a SignalPayload.
            ValueError: If threshold is negative.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("StepCounter: signal must be a SignalPayload")
        if not isinstance(threshold, (int, float)) or float(threshold) < 0:
            raise ValueError("StepCounter: threshold must be a non-negative number")
        fs = signal.frame.sample_rate_hz
        return await asyncio.to_thread(_count_steps, signal.data, fs)
