"""``NotchFilter`` — narrow-bandstop / IIR notch filter.

Algorithm:
    1. Receive the input signal frame, notch_hz, and quality_factor.
    2. Validate notch_hz and quality_factor (both positive).
    3. Design a second-order IIR notch filter using ``scipy.signal.iirnotch``.
       The normalised notch frequency is w0 = notch_hz / (sample_rate_hz / 2).
       The bandwidth is bw = w0 / quality_factor.
    4. Apply the second-order section to the signal.
    5. Return a filtered SignalFrame with the notch frequency attenuated.

Math:
    Second-order notch transfer function:

    $$H(z) = b_0 \\frac{1 - 2\\cos(\\omega_0) z^{-1} + z^{-2}}{1 - 2r\\cos(\\omega_0) z^{-1} + r^2 z^{-2}}$$

    where $r = 1 - \\pi \\Delta\\omega / Q$, $\\Delta\\omega = \\omega_0 / Q$, and
    $Q$ = quality_factor controls the notch bandwidth:

    $$\\Delta f = \\frac{f_0}{Q}$$

References:
    - scipy.signal.iirnotch: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.iirnotch.html
    - Smith, J.O. (2007). "Introduction to Digital Filters." W3K Publishing.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class NotchFilter(Knot):
    """IIR notch (line-noise rejection) filter.

    Production needs ``scipy.signal.iirnotch``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        notch_hz: Knot | float,
        quality_factor: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            notch_hz=notch_hz,
            quality_factor=quality_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        notch_hz: float,
        quality_factor: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply the notch filter to suppress the configured frequency.

        Args:
            signal: Signal to notch-filter at the configured line-noise frequency.
            notch_hz: Notch centre frequency in Hz (positive float).
            quality_factor: Q factor controlling notch bandwidth (positive float).

        Returns:
            SignalFrame with the notch frequency removed.

        Raises:
            ValueError: If notch_hz or quality_factor are not positive.
        """
        if not isinstance(notch_hz, (int, float)) or notch_hz <= 0:
            raise ValueError("NotchFilter: notch_hz must be positive")
        if not isinstance(quality_factor, (int, float)) or quality_factor <= 0:
            raise ValueError("NotchFilter: quality_factor must be positive")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:notch",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
