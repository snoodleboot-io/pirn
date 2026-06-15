"""``EegBandpassFilter`` — bandpass filter an EEG/MEG signal frame.

Algorithm:
    1. Receive a HealthSignalPayload, low_hz, and high_hz cutoffs.
    2. Validate that signal is a HealthSignalPayload and cutoffs are positive numbers with low_hz < high_hz.
    3. Design the bandpass filter (Butterworth IIR, order 4) at the specified cutoff frequencies.
    4. Apply zero-phase filtering via sosfiltfilt.
    5. Return a HealthSignalPayload with filtered data.

Math:
    Butterworth bandpass transfer function magnitude:

    |H(jw)|^2 = 1 / (1 + (w / wc)^(2n))

    where wc is the cutoff frequency and n = 4 is the filter order.

References:
    - SciPy butter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
    - SciPy sosfiltfilt: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload


def _apply_bandpass(data: np.ndarray, low_hz: float, high_hz: float, fs: float) -> np.ndarray:
    sos = ss.butter(4, [low_hz, high_hz], btype="bandpass", fs=fs, output="sos")
    return ss.sosfiltfilt(sos, data, axis=-1)


class EegBandpassFilter(Knot):
    """Bandpass-filter an EEG/MEG signal between two cutoff frequencies."""

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
        low_hz: Knot | float,
        high_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            low_hz=low_hz,
            high_hz=high_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: HealthSignalPayload,
        low_hz: float,
        high_hz: float,
        **_: Any,
    ) -> HealthSignalPayload:
        """Bandpass-filter the signal payload between the configured frequency cutoffs.

        Args:
            signal: The HealthSignalPayload to filter.
            low_hz: Lower cutoff frequency in Hz (positive number).
            high_hz: Upper cutoff frequency in Hz (positive number, must exceed low_hz).

        Returns:
            A HealthSignalPayload with the bandpass filter applied.

        Raises:
            TypeError: If signal is not a HealthSignalPayload.
            ValueError: If cutoffs are non-positive or low_hz >= high_hz.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("EegBandpassFilter: signal must be a HealthSignalPayload")
        if not isinstance(low_hz, (int, float)) or float(low_hz) <= 0:
            raise ValueError("EegBandpassFilter: low_hz must be a positive number")
        if not isinstance(high_hz, (int, float)) or float(high_hz) <= 0:
            raise ValueError("EegBandpassFilter: high_hz must be a positive number")
        if float(low_hz) >= float(high_hz):
            raise ValueError("EegBandpassFilter: low_hz must be < high_hz")

        fs = signal.frame.sample_rate_hz
        filtered = await asyncio.to_thread(
            _apply_bandpass, signal.data, float(low_hz), float(high_hz), fs
        )

        frame = HealthSignalFrame(
            signal_id=signal.frame.signal_id + ":bandpass",
            channel_count=signal.frame.channel_count,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=signal.frame.samples_per_channel,
            fetched_at=signal.frame.fetched_at,
        )
        return HealthSignalPayload(metadata=frame, data=filtered)
