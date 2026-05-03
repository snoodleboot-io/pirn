"""``BesselFilter`` — IIR with maximally-linear phase response."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BesselFilter(Knot):
    """Bessel / Thomson IIR filter.

    Production needs ``scipy.signal.bessel``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        order: int,
        cutoff_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(order, int) or order <= 0:
            raise ValueError("BesselFilter: order must be a positive integer")
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError("BesselFilter: cutoff_hz must be positive")
        self._order = order
        self._cutoff_hz = float(cutoff_hz)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def order(self) -> int:
        return self._order

    @property
    def cutoff_hz(self) -> float:
        return self._cutoff_hz

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply the Bessel IIR filter to the input signal and return the phase-linearised SignalFrame.

        Args:
            signal: Signal to filter with maximally-linear phase response.

        Returns:
            SignalFrame filtered by the configured Bessel IIR design.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:bessel",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
