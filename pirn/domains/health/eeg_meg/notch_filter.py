"""``NotchFilter`` — notch-filter at a specific frequency (e.g. 50/60 Hz).

Algorithm:
    1. Receive a SignalPayload and notch_hz frequency.
    2. Validate that signal is a SignalPayload and notch_hz is a positive number.
    3. Design a notch IIR filter via iirnotch, convert to SOS, and apply zero-phase filtering.
    4. Return a SignalPayload with filtered data.

Math:
    Second-order notch filter transfer function (Q = 30):

    H(z) = (1 - 2*cos(w0)*z^{-1} + z^{-2}) / (1 - 2*r*cos(w0)*z^{-1} + r^2*z^{-2})

    where w0 = 2*pi*f0/fs is the normalized notch frequency and r = 1 - pi*f0 / (Q * fs).

References:
    - SciPy iirnotch: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.iirnotch.html
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


def _apply_notch(data: np.ndarray, notch_hz: float, fs: float) -> np.ndarray:
    numerator_coeffs, denominator_coeffs = ss.iirnotch(notch_hz, Q=30.0, fs=fs)
    sos = ss.tf2sos(numerator_coeffs, denominator_coeffs)
    return ss.sosfiltfilt(sos, data, axis=-1)


class NotchFilter(Knot):
    """Apply a notch filter at the line-noise frequency."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
        notch_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            notch_hz=notch_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        notch_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply a notch filter at the configured frequency and return the filtered SignalPayload.

        Args:
            signal: The SignalPayload to filter.
            notch_hz: Positive frequency in Hz at which to apply the notch filter.

        Returns:
            A SignalPayload with the notch filter applied at the configured frequency.

        Raises:
            TypeError: If signal is not a SignalPayload.
            ValueError: If notch_hz is not a positive number.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("NotchFilter: signal must be a SignalPayload")
        if not isinstance(notch_hz, (int, float)) or float(notch_hz) <= 0:
            raise ValueError("NotchFilter: notch_hz must be a positive number")

        fs = signal.frame.sample_rate_hz
        filtered = await asyncio.to_thread(_apply_notch, signal.data, float(notch_hz), fs)

        frame = SignalFrame(
            signal_id=signal.frame.signal_id + ":notch",
            channel_count=signal.frame.channel_count,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=signal.frame.samples_per_channel,
            fetched_at=signal.frame.fetched_at,
        )
        return SignalPayload(metadata=frame, data=filtered)
