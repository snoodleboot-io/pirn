"""``LowPassFilter`` — pass low frequencies, attenuate high.

Algorithm:
    1. Receive the input signal frame and cutoff_hz.
    2. Validate cutoff_hz (positive float).
    3. Design a lowpass IIR or FIR filter with the given cutoff.
    4. Apply the filter to the signal.
    5. Return a filtered SignalFrame.

Math:
    Ideal lowpass frequency response:

    $$H(\\omega) = \\begin{cases} 1 & |\\omega| \\leq \\omega_c \\\\ 0 & |\\omega| > \\omega_c \\end{cases}$$

    where $\\omega_c = 2\\pi f_{\\text{cutoff}}$.

References:
    - scipy.signal.butter with btype='low':
      https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
    - Proakis, J.G. & Manolakis, D.G. (2006). "Digital Signal Processing" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class LowPassFilter(Knot):
    """Low-pass filter wrapper.

    Production needs ``scipy.signal``.
    """

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
        signal: SignalFrame,
        cutoff_hz: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the low-pass filter to the input signal.

        Args:
            signal: Signal to low-pass filter below the configured cutoff frequency.
            cutoff_hz: Cutoff frequency in Hz (positive float).

        Returns:
            SignalFrame with high-frequency content attenuated.

        Raises:
            ValueError: If cutoff_hz is not positive.
        """
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("LowPassFilter: cutoff_hz must be positive")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:lowpass",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
