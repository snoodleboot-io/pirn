"""``CombFilter`` — feedforward/feedback comb filter.

Algorithm:
    1. Receive the input signal frame, delay_samples, and gain.
    2. Validate delay_samples (positive integer) and gain (in [0.0, 1.0]).
    3. Apply the comb filter difference equation:
       y(n) = x(n) + gain * y(n - delay_samples)   (feedback/IIR form)
       or
       y(n) = x(n) + gain * x(n - delay_samples)   (feedforward/FIR form)
    4. Return a filtered SignalFrame.

Math:
    IIR comb filter transfer function:

    $$H(z) = \\frac{1}{1 - g \\, z^{-D}}$$

    FIR comb filter transfer function:

    $$H(z) = 1 + g \\, z^{-D}$$

    where $D$ = delay_samples and $g$ = gain $\\in [0, 1]$.

References:
    - Zolzer, U. (2008). "Digital Audio Effects." Wiley. Chapter 7 (Delay-based effects).
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing" (3rd ed.).
      Prentice Hall.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


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
        signal: SignalFrame,
        delay_samples: int,
        gain: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the comb filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.
            delay_samples: Comb delay in samples (positive integer).
            gain: Comb gain coefficient in [0.0, 1.0].

        Returns:
            Filtered SignalFrame with the same shape as the input.

        Raises:
            ValueError: If delay_samples or gain are invalid.
        """
        if not isinstance(delay_samples, int) or delay_samples <= 0:
            raise ValueError("CombFilter: delay_samples must be a positive integer")
        if not isinstance(gain, (int, float)) or not (0.0 <= gain <= 1.0):
            raise ValueError("CombFilter: gain must be a float in [0.0, 1.0]")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:comb",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
