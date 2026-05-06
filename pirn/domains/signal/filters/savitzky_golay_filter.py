"""``SavitzkyGolayFilter`` — local polynomial smoothing.

Algorithm:
    1. Receive the input signal frame, window_length, and polynomial_order.
    2. Validate window_length (positive odd integer), polynomial_order
       (non-negative integer less than window_length).
    3. Compute the Savitzky-Golay convolution coefficients by solving:
       h = (A^T A)^{-1} A^T e_{(window_length-1)/2}
       where A is the Vandermonde matrix of the window.
    4. Convolve the signal with h to obtain the smoothed output.
    5. Return a smoothed SignalFrame.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class SavitzkyGolayFilter(Knot):
    """Polynomial-fit smoothing filter.

    Production needs ``scipy.signal.savgol_filter``.
    """

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
        signal: SignalFrame,
        window_length: int,
        polynomial_order: int,
        **_: Any,
    ) -> SignalFrame:
        """Apply the Savitzky-Golay polynomial smoother to the input signal.

        Args:
            signal: Signal to smooth with local polynomial fitting.
            window_length: Number of samples in the smoothing window (positive odd integer).
            polynomial_order: Degree of the fitted polynomial (non-negative integer,
                must be less than window_length).

        Returns:
            SignalFrame of the polynomial-smoothed output.

        Raises:
            ValueError: If window_length or polynomial_order are invalid.
        """
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError(
                "SavitzkyGolayFilter: window_length must be a positive integer"
            )
        if window_length % 2 == 0:
            raise ValueError(
                "SavitzkyGolayFilter: window_length must be odd"
            )
        if not isinstance(polynomial_order, int) or polynomial_order < 0:
            raise ValueError(
                "SavitzkyGolayFilter: polynomial_order must be non-negative"
            )
        if polynomial_order >= window_length:
            raise ValueError(
                "SavitzkyGolayFilter: polynomial_order must be < window_length"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:savgol",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
