"""``FIRFilter`` — finite impulse response filter.

Algorithm:
    1. Receive the input signal payload and coefficients sequence.
    2. Validate that coefficients is non-empty and all values are real numbers.
    3. Apply via scipy.signal.lfilter(h, [1.0], data, axis=-1).
    4. Return a filtered SignalPayload.

Math:
    FIR convolution:

    $$y(n) = \\sum_{k=0}^{L-1} h(k) \\, x(n - k)$$

    where $h(k)$ are the FIR tap coefficients and $L$ is the filter length.
    The FIR filter has a linear phase response if and only if $h$ is symmetric.

References:
    - Parks, T.W. & Burrus, C.S. (1987). "Digital Filter Design." Wiley.
    - scipy.signal.lfilter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


class FIRFilter(Knot):
    """Apply a pre-designed FIR coefficient set."""

    def __init__(
        self,
        *,
        signal: Knot,
        coefficients: Knot | tuple,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            coefficients=coefficients,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        coefficients: Sequence[float],
        **_: Any,
    ) -> SignalPayload:
        """Convolve the configured FIR coefficients with the input signal.

        Args:
            signal: Signal payload to convolve with the FIR tap coefficients.
            coefficients: Non-empty sequence of real-valued FIR tap weights.

        Returns:
            SignalPayload of the FIR-filtered output.

        Raises:
            ValueError: If coefficients is empty.
            TypeError: If any coefficient is not a real number.
        """
        coeffs = tuple(coefficients)
        if not coeffs:
            raise ValueError("FIRFilter: coefficients must be non-empty")
        for c in coeffs:
            if not isinstance(c, (int, float)):
                raise TypeError("FIRFilter: every coefficient must be a real number")

        tap_weights = np.array(coeffs)
        filtered = await asyncio.to_thread(
            ss.lfilter, tap_weights, np.array([1.0]), signal.data, axis=-1
        )
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:fir",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
