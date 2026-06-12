"""``ChebyshevType1Filter`` — IIR with passband ripple, no stopband ripple.

Algorithm:
    1. Receive the input signal payload, order, passband_ripple_db, and cutoff_hz.
    2. Validate order, passband_ripple_db, and cutoff_hz (all positive).
    3. Design a Chebyshev Type-I IIR filter using ``scipy.signal.cheby1``.
    4. Apply the filter using second-order sections for numerical stability.
    5. Return a filtered SignalPayload.

Math:
    Chebyshev Type-I squared magnitude response:

    $$|H(j\\omega)|^2 = \\frac{1}{1 + \\varepsilon^2 T_n^2(\\omega / \\omega_c)}$$

    where $T_n$ is the Chebyshev polynomial of order $n$ and
    $\\varepsilon^2 = 10^{R_p/10} - 1$ with $R_p$ = passband_ripple_db.

References:
    - Chebyshev, P.L. (1853). "Théorie des mécanismes connus sous le nom de parallélogrammes."
    - scipy.signal.cheby1: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cheby1.html
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


class ChebyshevType1Filter(Knot):
    """Chebyshev Type-I IIR filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        passband_ripple_db: Knot | float,
        cutoff_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            passband_ripple_db=passband_ripple_db,
            cutoff_hz=cutoff_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        order: int,
        passband_ripple_db: float,
        cutoff_hz: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply the Chebyshev Type-I IIR filter to the input signal.

        Args:
            signal: Signal payload to filter with passband ripple and no stopband ripple.
            order: Filter order (positive integer).
            passband_ripple_db: Maximum passband ripple in dB (positive float).
            cutoff_hz: Cutoff frequency in Hz (positive float).

        Returns:
            SignalPayload filtered by the configured Chebyshev Type-I IIR.

        Raises:
            ValueError: If order, passband_ripple_db, or cutoff_hz are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ChebyshevType1Filter: order must be a positive integer")
        if not isinstance(passband_ripple_db, (int, float)) or passband_ripple_db <= 0:
            raise ValueError("ChebyshevType1Filter: passband_ripple_db must be positive")
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("ChebyshevType1Filter: cutoff_hz must be positive")

        fs = signal.frame.sample_rate_hz
        sos = await asyncio.to_thread(
            ss.cheby1, order, passband_ripple_db, cutoff_hz, btype="low", fs=fs, output="sos"
        )
        filtered = await asyncio.to_thread(ss.sosfilt, sos, signal.data, axis=-1)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:cheby1",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
