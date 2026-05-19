"""``SavitzkyGolayFilter`` — local polynomial smoothing.

Algorithm:
    1. Receive the input signal payload, window_length, and polynomial_order.
    2. Validate window_length (positive odd integer), polynomial_order
       (non-negative integer less than window_length).
    3. Apply scipy.signal.savgol_filter(data, window_length, polyorder, axis=-1).
    4. Return a smoothed SignalPayload.

Math:
    The Savitzky-Golay coefficients $\\{h_k\\}$ are chosen so that:

    $$y(n) = \\sum_{k=-(M-1)/2}^{(M-1)/2} h_k \\, x(n + k)$$

    fits a polynomial of degree $d$ (polynomial_order) to $M$ (window_length) points
    in the least-squares sense. This is equivalent to fitting a local polynomial and
    evaluating it at the window centre.

References:
    - Savitzky, A. & Golay, M.J.E. (1964). "Smoothing and differentiation of data by
      simplified least squares procedures." Anal. Chemistry, 36(8), 1627-1639.
    - scipy.signal.savgol_filter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.savgol_filter.html
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


class SavitzkyGolayFilter(Knot):
    """Polynomial-fit smoothing filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        window_length: Knot | int,
        polynomial_order: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            window_length=window_length,
            polynomial_order=polynomial_order,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        window_length: int,
        polynomial_order: int,
        **_: Any,
    ) -> SignalPayload:
        """Apply the Savitzky-Golay polynomial smoother to the input signal.

        Args:
            signal: Signal payload to smooth with local polynomial fitting.
            window_length: Number of samples in the smoothing window (positive odd integer).
            polynomial_order: Degree of the fitted polynomial (non-negative integer,
                must be less than window_length).

        Returns:
            SignalPayload of the polynomial-smoothed output.

        Raises:
            ValueError: If window_length or polynomial_order are invalid.
        """
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError("SavitzkyGolayFilter: window_length must be a positive integer")
        if window_length % 2 == 0:
            raise ValueError("SavitzkyGolayFilter: window_length must be odd")
        if not isinstance(polynomial_order, int) or polynomial_order < 0:
            raise ValueError("SavitzkyGolayFilter: polynomial_order must be non-negative")
        if polynomial_order >= window_length:
            raise ValueError("SavitzkyGolayFilter: polynomial_order must be < window_length")

        filtered = await asyncio.to_thread(
            ss.savgol_filter, signal.data, window_length, polynomial_order, axis=-1
        )
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:savgol",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.data.shape[-1],
            ),
            data=np.asarray(filtered),
        )
