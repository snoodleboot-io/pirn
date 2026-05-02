"""``ChebyshevType1Filter`` — IIR with passband ripple, no stopband ripple."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ChebyshevType1Filter(Knot):
    """Chebyshev Type-I IIR filter.

    Production needs ``scipy.signal.cheby1``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        order: int,
        passband_ripple_db: float,
        cutoff_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(order, int) or order <= 0:
            raise ValueError(
                "ChebyshevType1Filter: order must be a positive integer"
            )
        if not isinstance(passband_ripple_db, (int, float)) or passband_ripple_db <= 0:
            raise ValueError(
                "ChebyshevType1Filter: passband_ripple_db must be positive"
            )
        if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
            raise ValueError(
                "ChebyshevType1Filter: cutoff_hz must be positive"
            )
        self._order = order
        self._passband_ripple_db = float(passband_ripple_db)
        self._cutoff_hz = float(cutoff_hz)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def order(self) -> int:
        return self._order

    @property
    def passband_ripple_db(self) -> float:
        return self._passband_ripple_db

    @property
    def cutoff_hz(self) -> float:
        return self._cutoff_hz

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:cheby1",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
