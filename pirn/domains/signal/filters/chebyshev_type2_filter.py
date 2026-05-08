"""``ChebyshevType2Filter`` — IIR with stopband ripple, flat passband.

Algorithm:
    1. Receive the input signal payload, order, stopband_attenuation_db, and cutoff_hz.
    2. Validate order, stopband_attenuation_db, and cutoff_hz (all positive).
    3. Design a Chebyshev Type-II IIR filter using ``scipy.signal.cheby2``.
    4. Apply the filter using second-order sections for numerical stability.
    5. Return a filtered SignalPayload.

Math:
    Chebyshev Type-II squared magnitude response:

    $$|H(j\\omega)|^2 = \\frac{1}{1 + \\left( \\varepsilon^2 T_n^2(\\omega_s / \\omega_c) / T_n^2(\\omega_s / \\omega) \\right)^{-1}}$$

    where $\\varepsilon^2 = (10^{R_s/10} - 1)^{-1}$ and $R_s$ = stopband_attenuation_db.
    The passband is maximally flat; ripple is confined to the stopband.

References:
    - scipy.signal.cheby2: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cheby2.html
    - Williams, A.B. & Taylor, F.J. (2006). "Electronic Filter Design Handbook" (4th ed.).
      McGraw-Hill.
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


class ChebyshevType2Filter(Knot):
    """Chebyshev Type-II IIR filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        stopband_attenuation_db: Knot | float,
        cutoff_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            stopband_attenuation_db=stopband_attenuation_db,
            cutoff_hz=cutoff_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        order: int,
        stopband_attenuation_db: float,
        cutoff_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply the Chebyshev Type-II IIR filter to the input signal.

        Args:
            signal: Signal payload to filter with stopband ripple and a flat passband.
            order: Filter order (positive integer).
            stopband_attenuation_db: Minimum stopband attenuation in dB (positive float).
            cutoff_hz: Cutoff frequency in Hz (positive float).

        Returns:
            SignalPayload filtered by the configured Chebyshev Type-II IIR.

        Raises:
            ValueError: If order, stopband_attenuation_db, or cutoff_hz are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ChebyshevType2Filter: order must be a positive integer")
        if not isinstance(stopband_attenuation_db, (int, float)) or stopband_attenuation_db <= 0:
            raise ValueError("ChebyshevType2Filter: stopband_attenuation_db must be positive")
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("ChebyshevType2Filter: cutoff_hz must be positive")

        fs = signal.frame.sample_rate_hz
        sos = await asyncio.to_thread(
            ss.cheby2, order, stopband_attenuation_db, cutoff_hz, btype="low", fs=fs, output="sos"
        )
        filtered = await asyncio.to_thread(ss.sosfilt, sos, signal.data, axis=-1)
        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:cheby2",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
