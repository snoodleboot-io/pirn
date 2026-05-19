"""``SeizureDetector`` — detect seizure intervals in an EEG.

Algorithm:
    1. Receive a SignalPayload and threshold float.
    2. Validate that signal is a SignalPayload and threshold is non-negative.
    3. Compute RMS energy in sliding 1-second windows across all channels.
    4. Mark windows where RMS exceeds threshold as candidate seizures.
    5. Return a sequence of (start_sec, end_sec) interval tuples.

Math:
    Root-mean-square energy in a window of N samples:

    RMS = sqrt(1/N * sum_{i=1}^{N} x_i^2)

References:
    - Shoeb & Guttag (2010) Application of Machine Learning to Epileptic Seizure Detection.
    - PhysioNet EEG seizure dataset: https://physionet.org/content/chbmit/1.0.0/
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_payload import SignalPayload


def _detect_seizures(data: np.ndarray, fs: float, threshold: float) -> list[tuple[float, float]]:
    window_samples = max(1, int(fs))
    channel_data = data if data.ndim == 1 else data[0]
    n_samples = len(channel_data)
    intervals: list[tuple[float, float]] = []
    in_seizure = False
    start_sec = 0.0
    for i in range(0, n_samples, window_samples):
        window = channel_data[i : i + window_samples]
        rms = float(np.sqrt(np.mean(window**2)))
        window_start = i / fs
        window_end = min((i + window_samples) / fs, n_samples / fs)
        if rms > threshold:
            if not in_seizure:
                in_seizure = True
                start_sec = window_start
        else:
            if in_seizure:
                in_seizure = False
                intervals.append((start_sec, window_end))
    if in_seizure:
        intervals.append((start_sec, n_samples / fs))
    return intervals


class SeizureDetector(Knot):
    """Detect candidate seizure intervals in an EEG signal."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            threshold=threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        threshold: float,
        **_: Any,
    ) -> Sequence[tuple[float, float]]:
        """Detect seizure intervals in the EEG signal above the configured threshold.

        Args:
            signal: The EEG SignalPayload to scan for seizures.
            threshold: Non-negative RMS energy detection threshold.

        Returns:
            A sequence of (start_sec, end_sec) tuples representing detected seizure intervals.

        Raises:
            TypeError: If signal is not a SignalPayload or threshold is not numeric.
            ValueError: If threshold is negative.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("SeizureDetector: signal must be a SignalPayload")
        if not isinstance(threshold, (int, float)):
            raise TypeError("SeizureDetector: threshold must be numeric")
        if float(threshold) < 0:
            raise ValueError("SeizureDetector: threshold must be non-negative")

        fs = signal.frame.sample_rate_hz
        return await asyncio.to_thread(_detect_seizures, signal.data, fs, float(threshold))
