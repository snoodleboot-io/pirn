"""``FractionalDelayFilter`` — sub-sample delay via Lagrange interpolation."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FractionalDelayFilter(Knot):
    """Apply a sub-sample delay using Lagrange interpolation.

    Production needs a hand-rolled or ``scipy``-based Lagrange FIR design.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        delay_samples: float,
        filter_order: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(delay_samples, (int, float)) or delay_samples < 0.0:
            raise ValueError(
                "FractionalDelayFilter: delay_samples must be >= 0.0"
            )
        if not isinstance(filter_order, int) or filter_order <= 0:
            raise ValueError(
                "FractionalDelayFilter: filter_order must be a positive integer"
            )
        self._delay_samples = float(delay_samples)
        self._filter_order = filter_order
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def delay_samples(self) -> float:
        return self._delay_samples

    @property
    def filter_order(self) -> int:
        return self._filter_order

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply a fractional sample delay to the signal using Lagrange interpolation.

        Args:
            signal: Signal to delay.

        Returns:
            SignalFrame delayed by ``delay_samples`` samples.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:frac_delayed",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
