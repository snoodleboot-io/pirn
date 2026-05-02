"""``SavitzkyGolayFilter`` — local polynomial smoothing."""

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
        window_length: int,
        polynomial_order: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._window_length = window_length
        self._polynomial_order = polynomial_order
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def window_length(self) -> int:
        return self._window_length

    @property
    def polynomial_order(self) -> int:
        return self._polynomial_order

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:savgol",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
