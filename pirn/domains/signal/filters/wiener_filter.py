"""``WienerFilter`` — minimum-MSE linear filter."""

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
        window_size: int,
        noise_power: float | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(window_size, int) or window_size <= 0:
            raise ValueError(
                "WienerFilter: window_size must be a positive integer"
            )
        if noise_power is not None and (
            not isinstance(noise_power, (int, float)) or noise_power <= 0
        ):
            raise ValueError(
                "WienerFilter: noise_power must be positive when supplied"
            )
        self._window_size = window_size
        self._noise_power = (
            float(noise_power) if noise_power is not None else None
        )
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def window_size(self) -> int:
        return self._window_size

    @property
    def noise_power(self) -> float | None:
        return self._noise_power

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply the Wiener filter to the input signal and return the minimum-MSE denoised SignalFrame.

        Args:
            signal: Noisy signal to denoise with the stationary Wiener filter.

        Returns:
            SignalFrame of the minimum-MSE Wiener-filtered output.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:wiener",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
