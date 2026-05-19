"""``HighPassFilter`` — pass high frequencies, attenuate low.

Algorithm:
    1. Receive the input signal payload and cutoff_hz.
    2. Validate cutoff_hz (positive float).
    3. Design a highpass Butterworth IIR filter with the given cutoff.
    4. Apply the filter to the signal data.
    5. Return a filtered SignalPayload.

Math:
    Ideal highpass frequency response:

    $$H(\\omega) = \\begin{cases} 0 & |\\omega| < \\omega_c \\\\ 1 & |\\omega| \\geq \\omega_c \\end{cases}$$

    where $\\omega_c = 2\\pi f_{\\text{cutoff}}$.

References:
    - scipy.signal.butter with btype='high':
      https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
    - Proakis, J.G. & Manolakis, D.G. (2006). "Digital Signal Processing" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


class HighPassFilter(Knot):
    """High-pass Butterworth filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        cutoff_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            cutoff_hz=cutoff_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        cutoff_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply the high-pass filter to the input signal.

        Args:
            signal: Signal payload to high-pass filter above the configured cutoff frequency.
            cutoff_hz: Cutoff frequency in Hz (positive float).

        Returns:
            SignalPayload with low-frequency content attenuated.

        Raises:
            ValueError: If cutoff_hz is not positive.
        """
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("HighPassFilter: cutoff_hz must be positive")

        fs = signal.frame.sample_rate_hz
        sos = await asyncio.to_thread(ss.butter, 4, cutoff_hz, btype="high", fs=fs, output="sos")
        filtered = await asyncio.to_thread(ss.sosfilt, sos, signal.data, axis=-1)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:highpass",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
