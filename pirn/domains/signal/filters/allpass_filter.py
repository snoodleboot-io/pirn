"""``AllpassFilter`` — phase-shifting allpass IIR filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AllpassFilter(Knot):
    """Apply a first-order allpass IIR filter to shift phase without altering magnitude."""

    def __init__(
        self,
        *,
        signal: Knot,
        pole_radius: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pole_radius, (int, float)) or not (0.0 < pole_radius < 1.0):
            raise ValueError(
                "AllpassFilter: pole_radius must be a float in the open interval (0, 1)"
            )
        self._pole_radius = float(pole_radius)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def pole_radius(self) -> float:
        return self._pole_radius

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the allpass IIR filter and return a phase-shifted SignalFrame.

        Args:
            signal: The input signal frame.

        Returns:
            SignalFrame with identical shape and updated signal_id.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:allpass",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
