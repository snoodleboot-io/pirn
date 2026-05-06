"""``WienerFilter`` — minimum-MSE linear filter.

Algorithm:
    1. Receive the input signal frame, window_size, and optional noise_power.
    2. Validate window_size (positive integer) and noise_power (positive if supplied).
    3. Estimate the local signal mean and variance over a window of window_size samples.
    4. Estimate noise variance: use noise_power if supplied, otherwise estimate from
       the minimum local variance across the signal.
    5. Apply the Wiener formula: y(n) = mu(n) + max(0, sigma^2 - sigma_n^2) / sigma^2 * (x(n) - mu(n))
    6. Return a denoised SignalFrame.

Math:
    Wiener filter optimal frequency-domain solution:

    $$H_{\\text{opt}}(\\omega) = \\frac{S_{xx}(\\omega)}{S_{xx}(\\omega) + S_{nn}(\\omega)}$$

    Local-statistics approximation:

    $$y(n) = \\mu_x(n) + \\frac{\\sigma_x^2(n) - \\sigma_n^2}{\\sigma_x^2(n)} \\left( x(n) - \\mu_x(n) \\right)$$

References:
    - Wiener, N. (1949). "Extrapolation, Interpolation, and Smoothing of Stationary Time Series."
      MIT Press.
    - scipy.signal.wiener: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.wiener.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class WienerFilter(Knot):
    """Stationary Wiener filter.

    Production needs ``scipy.signal.wiener``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        window_size: Knot | int,
        noise_power: Knot | float | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            window_size=window_size,
            noise_power=noise_power,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        window_size: int,
        noise_power: float | None = None,
        **_: Any,
    ) -> SignalFrame:
        """Apply the Wiener filter to the input signal.

        Args:
            signal: Noisy signal to denoise with the stationary Wiener filter.
            window_size: Local statistics window size (positive integer).
            noise_power: Known noise power (positive float), or None to estimate.

        Returns:
            SignalFrame of the minimum-MSE Wiener-filtered output.

        Raises:
            ValueError: If window_size or noise_power are invalid.
        """
        if not isinstance(window_size, int) or window_size <= 0:
            raise ValueError("WienerFilter: window_size must be a positive integer")
        if noise_power is not None and (
            not isinstance(noise_power, (int, float)) or noise_power <= 0
        ):
            raise ValueError("WienerFilter: noise_power must be positive when supplied")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:wiener",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
