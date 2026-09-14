"""``LowPassFilter`` — pass low frequencies, attenuate high.

Algorithm:
    1. Receive the input signal payload, cutoff_hz, and order.
    2. Validate cutoff_hz (positive float) and order (positive integer).
    3. Design a lowpass Butterworth IIR filter of the given order and cutoff
       via :class:`ButterworthDesign`.
    4. Apply the filter to the signal data.
    5. Return a filtered SignalPayload.

Math:
    Butterworth lowpass squared magnitude response:

    $$|H(j\\omega)|^2 = \\frac{1}{1 + (\\omega / \\omega_c)^{2n}}$$

    where $n$ = order and $\\omega_c = 2\\pi f_{\\text{cutoff}}$. The -3 dB point
    occurs exactly at $\\omega_c$; the response is maximally flat in the passband
    and rolls off at $-20n$ dB/decade beyond $\\omega_c$.

References:
    - Butterworth, S. (1930). "On the theory of filter amplifiers." Wireless Engineer, 7, 536-541.
    - scipy.signal.butter with btype='low':
      https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html
    - Proakis, J.G. & Manolakis, D.G. (2006). "Digital Signal Processing" (4th ed.). Prentice Hall.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.filters._butterworth_design import ButterworthDesign
from pirn_signal.types.signal_payload import SignalPayload


class LowPassFilter(Knot):
    """Low-pass Butterworth filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        cutoff_hz: Knot | float,
        order: Knot | int = 4,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            cutoff_hz=cutoff_hz,
            order=order,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        cutoff_hz: float,
        order: int = 4,
        **_: Any,
    ) -> SignalPayload:
        """Apply the low-pass filter to the input signal.

        Args:
            signal: Signal payload to low-pass filter below the configured cutoff frequency.
            cutoff_hz: Cutoff frequency in Hz (positive float).
            order: Butterworth filter order (positive integer, default 4).

        Returns:
            SignalPayload with high-frequency content attenuated.

        Raises:
            ValueError: If cutoff_hz or order are invalid.
        """
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("LowPassFilter: cutoff_hz must be positive")
        if not isinstance(order, int) or order <= 0:
            raise ValueError("LowPassFilter: order must be a positive integer")

        fs = signal.frame.sample_rate_hz
        filtered = await asyncio.to_thread(
            ButterworthDesign.design_and_apply, signal.data, order, cutoff_hz, "lowpass", fs
        )
        return signal.derive("lowpass", filtered)
