# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``BandStopFilter`` — reject a frequency band, pass elsewhere.

Algorithm:
    1. Receive the input signal payload, low_cutoff_hz, high_cutoff_hz, and order.
    2. Validate that both cutoffs are positive, low_cutoff_hz < high_cutoff_hz, and
       order is a positive integer.
    3. Design a bandstop Butterworth IIR filter of the given order and edge
       frequencies via :class:`ButterworthDesign`.
    4. Apply the filter to the signal data.
    5. Return a filtered SignalPayload.

Math:
    Butterworth bandstop squared magnitude response, obtained via the lowpass-to-bandpass
    frequency transform with center frequency $\\omega_0 = \\sqrt{\\omega_L \\omega_H}$ and
    bandwidth $B = \\omega_H - \\omega_L$:

    $$\\omega' = \\frac{\\omega^2 - \\omega_0^2}{\\omega B}$$

    $$|H(j\\omega)|^2 = \\frac{1}{1 + (1 / \\omega')^{2n}}$$

    where $n$ = order, $\\omega_L = 2\\pi f_{\\text{low}}$, and $\\omega_H = 2\\pi f_{\\text{high}}$.
    The response is zero at $\\omega_0$ (the notch) and rises to -3 dB at $\\omega_L$ and $\\omega_H$.

References:
    - Butterworth, S. (1930). "On the theory of filter amplifiers." Wireless Engineer, 7, 536-541.
    - scipy.signal.butter with btype='bandstop':
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


class BandStopFilter(Knot):
    """Band-stop Butterworth filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        low_cutoff_hz: Knot | float,
        high_cutoff_hz: Knot | float,
        order: Knot | int = 4,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            low_cutoff_hz=low_cutoff_hz,
            high_cutoff_hz=high_cutoff_hz,
            order=order,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        low_cutoff_hz: float,
        high_cutoff_hz: float,
        order: int = 4,
        **_: Any,
    ) -> SignalPayload:
        """Apply the band-stop filter to the input signal.

        Args:
            signal: Signal payload to band-stop filter.
            low_cutoff_hz: Lower edge of the stop band in Hz (positive float).
            high_cutoff_hz: Upper edge of the stop band in Hz (must exceed low_cutoff_hz).
            order: Butterworth filter order (positive integer, default 4).

        Returns:
            SignalPayload with the configured frequency band attenuated.

        Raises:
            ValueError: If cutoff frequencies or order are invalid.
        """
        if not isinstance(low_cutoff_hz, (int, float)) or low_cutoff_hz <= 0:
            raise ValueError("BandStopFilter: low_cutoff_hz must be positive")
        if not isinstance(high_cutoff_hz, (int, float)) or high_cutoff_hz <= 0:
            raise ValueError("BandStopFilter: high_cutoff_hz must be positive")
        if low_cutoff_hz >= high_cutoff_hz:
            raise ValueError("BandStopFilter: low_cutoff_hz must be < high_cutoff_hz")
        if not isinstance(order, int) or order <= 0:
            raise ValueError("BandStopFilter: order must be a positive integer")

        fs = signal.frame.sample_rate_hz
        filtered = await asyncio.to_thread(
            ButterworthDesign.design_and_apply,
            signal.data,
            order,
            (low_cutoff_hz, high_cutoff_hz),
            "bandstop",
            fs,
        )
        return signal.derive("bandstop", filtered)
