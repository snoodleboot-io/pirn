"""``AllpassFilter`` — phase-shifting allpass IIR filter.

Algorithm:
    1. Receive the input signal frame and pole_radius.
    2. Validate pole_radius is in the open interval (0, 1) for stability.
    3. Construct the first-order allpass transfer function:
       H(z) = (z^{-1} - a) / (1 - a * z^{-1})  where a = -pole_radius.
    4. Apply the filter using direct-form II transposed structure.
    5. Return a SignalFrame with unchanged shape and updated signal_id.

Math:
    First-order allpass transfer function:

    $$H(z) = \\frac{z^{-1} - a}{1 - a z^{-1}}, \\quad a = -r$$

    where $r \\in (0, 1)$ is the pole_radius. The pole is at $z = a$ inside the
    unit circle, guaranteeing stability. The magnitude response is unity: $|H(e^{j\\omega})| = 1$.

References:
    - Zolzer, U. (2008). "Digital Audio Effects." Wiley. Chapter 2.
    - Oppenheim, A.V. & Schafer, R.W. (2009). "Discrete-Time Signal Processing" (3rd ed.).
      Prentice Hall. Section 5.7.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AllpassFilter(Knot):
    """Apply a first-order allpass IIR filter to shift phase without altering magnitude."""

    def __init__(
        self,
        *,
        signal: Knot,
        pole_radius: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            pole_radius=pole_radius,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        pole_radius: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the allpass IIR filter and return a phase-shifted SignalFrame.

        Args:
            signal: The input signal frame.
            pole_radius: Pole radius in the open interval (0, 1).

        Returns:
            SignalFrame with identical shape and updated signal_id.

        Raises:
            ValueError: If pole_radius is not in (0, 1).
        """
        if not isinstance(pole_radius, (int, float)) or not (0.0 < pole_radius < 1.0):
            raise ValueError(
                "AllpassFilter: pole_radius must be a float in the open interval (0, 1)"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:allpass",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
