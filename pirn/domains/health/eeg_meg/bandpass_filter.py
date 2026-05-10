"""``BandpassFilter`` — bandpass filter an EEG/MEG signal frame.

Algorithm:
    1. Receive a SignalPayload, low_hz, and high_hz cutoffs.
    2. Validate that signal is a SignalPayload and cutoffs are positive numbers with low_hz < high_hz.
    3. Design the bandpass filter (Butterworth IIR, order 4) at the specified cutoff frequencies.
    4. Apply zero-phase filtering via sosfiltfilt.
    5. Return a SignalPayload with filtered data.

References:
    - SciPy butter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
    - SciPy sosfiltfilt: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload


def _apply_bandpass(data: np.ndarray, low_hz: float, high_hz: float, fs: float) -> np.ndarray:
    sos = ss.butter(4, [low_hz, high_hz], btype="bandpass", fs=fs, output="sos")
    return ss.sosfiltfilt(sos, data, axis=-1)


class BandpassFilter(Knot):
    """Bandpass-filter an EEG/MEG signal between two cutoff frequencies."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
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
        signal: SignalPayload,
        low_hz: float,
        high_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Bandpass-filter the signal payload between the configured frequency cutoffs.

        Args:
            signal: The SignalPayload to filter.
            low_hz: Lower cutoff frequency in Hz (positive number).
            high_hz: Upper cutoff frequency in Hz (positive number, must exceed low_hz).

        Returns:
            A SignalPayload with the bandpass filter applied.

        Raises:
            TypeError: If signal is not a SignalPayload.
            ValueError: If cutoffs are non-positive or low_hz >= high_hz.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("BandpassFilter: signal must be a SignalPayload")
        if not isinstance(low_hz, (int, float)) or float(low_hz) <= 0:
            raise ValueError("BandpassFilter: low_hz must be a positive number")
        if not isinstance(high_hz, (int, float)) or float(high_hz) <= 0:
            raise ValueError("BandpassFilter: high_hz must be a positive number")
        if float(low_hz) >= float(high_hz):
            raise ValueError("BandpassFilter: low_hz must be < high_hz")

        fs = signal.frame.sample_rate_hz
        filtered = await asyncio.to_thread(
            _apply_bandpass, signal.data, float(low_hz), float(high_hz), fs
        )

        frame = SignalFrame(
            signal_id=signal.frame.signal_id + ":bandpass",
            channel_count=signal.frame.channel_count,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=signal.frame.samples_per_channel,
            fetched_at=signal.frame.fetched_at,
        )
        return SignalPayload(metadata=frame, data=filtered)
