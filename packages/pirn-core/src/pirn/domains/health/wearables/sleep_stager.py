"""``SleepStager`` — stage sleep epochs as wake / N1 / N2 / N3 / REM.

Algorithm:
    1. Receive signal (HealthSignalPayload) and epoch_length_sec float.
    2. Validate signal is a HealthSignalPayload and epoch_length_sec is positive numeric.
    3. Divide signal into fixed-length epochs.
    4. Compute band power per epoch (delta, theta, alpha, beta via scipy.signal.welch).
    5. Apply rule-based staging: high delta → N3, high theta → N2, high alpha → wake.

Math:
    Number of epochs:

    $$N_{\\text{epochs}} = \\left\\lfloor \\frac{T_{\\text{total}}}{T_{\\text{epoch}}} \\right\\rfloor$$

    where $T_{\\text{total}} = \\text{samples\\_per\\_channel} / \\text{sample\\_rate\\_hz}$.

References:
    - Rechtschaffen, A. & Kales, A. (1968). A Manual of Standardized Terminology.
    - YASA: https://raphaelvallat.com/yasa/
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import scipy.signal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload


def _band_power(epoch: np.ndarray, fs: float, low: float, high: float) -> float:
    """Compute average power in a frequency band using Welch's method."""
    nperseg = min(epoch.size, max(4, int(fs * 2)))
    freqs, psd = scipy.signal.welch(epoch, fs=fs, nperseg=nperseg)
    idx = (freqs >= low) & (freqs <= high)
    return float(np.trapezoid(psd[idx], freqs[idx])) if idx.any() else 0.0


def _stage_epoch(epoch: np.ndarray, fs: float) -> str:
    """Classify a single EEG epoch into a sleep stage.

    Args:
        epoch: 1-D array of EEG samples for one epoch.
        fs: Sampling rate in Hz.

    Returns:
        Stage label string: ``"N3"``, ``"N2"``, ``"N1"``, or ``"wake"``.
    """
    delta = _band_power(epoch, fs, 0.5, 4.0)
    theta = _band_power(epoch, fs, 4.0, 8.0)
    alpha = _band_power(epoch, fs, 8.0, 13.0)
    total = delta + theta + alpha + 1e-12
    if delta / total > 0.5:
        return "N3"
    if theta / total > 0.4:
        return "N2"
    if alpha / total > 0.3:
        return "wake"
    return "N1"


def _stage_all_epochs(data: np.ndarray, fs: float, epoch_samples: int) -> tuple[str, ...]:
    """Stage all epochs in a signal array.

    Args:
        data: 1-D EEG array.
        fs: Sampling rate in Hz.
        epoch_samples: Number of samples per epoch.

    Returns:
        Tuple of stage label strings, one per epoch.
    """
    n_epochs = max(1, len(data) // epoch_samples)
    stages: list[str] = []
    for i in range(n_epochs):
        epoch = data[i * epoch_samples : (i + 1) * epoch_samples]
        stages.append(_stage_epoch(epoch, fs))
    return tuple(stages)


class SleepStager(Knot):
    """Stage sleep from a long PSG / single-channel EEG signal."""

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
        epoch_length_sec: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal, epoch_length_sec=epoch_length_sec, _config=_config, **kwargs
        )

    async def process(
        self,
        signal: HealthSignalPayload,
        epoch_length_sec: float,
        **_: Any,
    ) -> tuple[str, ...]:
        """Stage the signal into sleep epochs and return a tuple of stage labels.

        Args:
            signal: HealthSignalPayload containing the PSG or EEG recording.
            epoch_length_sec: Epoch duration in seconds (must be positive).

        Returns:
            Tuple of stage label strings (e.g. ``"wake"``, ``"N1"``, ``"N3"``) one per epoch.

        Raises:
            TypeError: If signal is not a HealthSignalPayload or epoch_length_sec is not numeric.
            ValueError: If epoch_length_sec is not positive.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("SleepStager: signal must be a HealthSignalPayload")
        if not isinstance(epoch_length_sec, (int, float)):
            raise TypeError("SleepStager: epoch_length_sec must be numeric")
        if float(epoch_length_sec) <= 0:
            raise ValueError("SleepStager: epoch_length_sec must be positive")
        eeg = signal.data if signal.data.ndim == 1 else signal.data[0]
        fs = signal.frame.sample_rate_hz
        epoch_samples = max(1, int(epoch_length_sec * fs))
        return await asyncio.to_thread(_stage_all_epochs, eeg, fs, epoch_samples)
