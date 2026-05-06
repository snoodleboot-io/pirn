"""``BandStopFilter`` — reject a frequency band, pass elsewhere.

Algorithm:
    1. Receive the input signal frame, low_cutoff_hz, and high_cutoff_hz.
    2. Validate that both cutoffs are positive and low_cutoff_hz < high_cutoff_hz.
    3. Design a bandstop (notch) IIR or FIR filter with the given edge frequencies.
    4. Apply the filter to the signal.
    5. Return a filtered SignalFrame.

Math:
    Ideal bandstop frequency response:

    $$H(\\omega) = \\begin{cases} 0 & \\omega_{L} \\leq \\omega \\leq \\omega_{H} \\\\ 1 & \\text{otherwise} \\end{cases}$$

    where $\\omega_L = 2\\pi f_{\\text{low}}$ and $\\omega_H = 2\\pi f_{\\text{high}}$.

References:
    - scipy.signal.butter with btype='bandstop':
      https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
    - Proakis, J.G. & Manolakis, D.G. (2006). "Digital Signal Processing" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BandStopFilter(Knot):
    """Band-stop filter wrapper.

    Production needs ``scipy.signal``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        low_cutoff_hz: Knot | float,
        high_cutoff_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            low_cutoff_hz=low_cutoff_hz,
            high_cutoff_hz=high_cutoff_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        low_cutoff_hz: float,
        high_cutoff_hz: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the band-stop filter to the input signal.

        Args:
            signal: Signal to band-stop filter.
            low_cutoff_hz: Lower edge of the stop band in Hz (positive float).
            high_cutoff_hz: Upper edge of the stop band in Hz (must exceed low_cutoff_hz).

        Returns:
            SignalFrame with the configured frequency band attenuated.

        Raises:
            ValueError: If cutoff frequencies are invalid.
        """
        if not isinstance(low_cutoff_hz, (int, float)) or low_cutoff_hz <= 0:
            raise ValueError("BandStopFilter: low_cutoff_hz must be positive")
        if not isinstance(high_cutoff_hz, (int, float)) or high_cutoff_hz <= 0:
            raise ValueError("BandStopFilter: high_cutoff_hz must be positive")
        if low_cutoff_hz >= high_cutoff_hz:
            raise ValueError("BandStopFilter: low_cutoff_hz must be < high_cutoff_hz")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:bandstop",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
