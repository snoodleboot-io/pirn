"""``CombFilter`` — feedforward comb filter.

Algorithm:
    1. Receive the input signal payload, delay_samples, and gain.
    2. Validate delay_samples (positive integer) and gain (in [0.0, 1.0]).
    3. Build FIR numerator: b[0]=1.0, b[delay_samples]=feedback_gain.
    4. Apply via scipy.signal.lfilter(b, [1.0], data, axis=-1).
    5. Return a filtered SignalPayload.

Math:
    FIR comb filter transfer function:

    $$H(z) = 1 + g \\, z^{-D}$$

    where $D$ = delay_samples and $g$ = gain $\\in [0, 1]$.

References:
    - Zolzer, U. (2008). "Digital Audio Effects." Wiley. Chapter 7 (Delay-based effects).
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing" (3rd ed.).
      Prentice Hall.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


class CombFilter(Knot):
    """Apply a comb filter with a fixed delay and gain coefficient."""

    def __init__(
        self,
        *,
        signal: Knot,
        delay_samples: Knot | int,
        gain: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            delay_samples=delay_samples,
            gain=gain,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        delay_samples: int,
        gain: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply the comb filter and return the filtered SignalPayload.

        Args:
            signal: The input signal payload.
            delay_samples: Comb delay in samples (positive integer).
            gain: Comb gain coefficient in [0.0, 1.0].

        Returns:
            Filtered SignalPayload with the same shape as the input.

        Raises:
            ValueError: If delay_samples or gain are invalid.
        """
        if not isinstance(delay_samples, int) or delay_samples <= 0:
            raise ValueError("CombFilter: delay_samples must be a positive integer")
        if not isinstance(gain, (int, float)) or not (0.0 <= gain <= 1.0):
            raise ValueError("CombFilter: gain must be a float in [0.0, 1.0]")

        numerator_coeffs = np.zeros(delay_samples + 1)
        numerator_coeffs[0] = 1.0
        numerator_coeffs[-1] = gain
        filtered = await asyncio.to_thread(
            ss.lfilter, numerator_coeffs, np.array([1.0]), signal.data, axis=-1
        )
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:comb",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
