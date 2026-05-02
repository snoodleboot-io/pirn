"""``IIRFilter`` — generic infinite impulse response filter."""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class IIRFilter(Knot):
    """Apply a pre-designed IIR (b, a) coefficient set.

    Production needs ``scipy.signal.lfilter`` or ``sosfiltfilt``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        numerator: Sequence[float],
        denominator: Sequence[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        b = tuple(numerator)
        a = tuple(denominator)
        if not b:
            raise ValueError("IIRFilter: numerator must be non-empty")
        if not a:
            raise ValueError("IIRFilter: denominator must be non-empty")
        if a[0] == 0:
            raise ValueError("IIRFilter: denominator[0] must be non-zero")
        for c in (*b, *a):
            if not isinstance(c, (int, float)):
                raise TypeError(
                    "IIRFilter: every coefficient must be a real number"
                )
        self._numerator = tuple(float(c) for c in b)
        self._denominator = tuple(float(c) for c in a)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def numerator(self) -> tuple[float, ...]:
        return self._numerator

    @property
    def denominator(self) -> tuple[float, ...]:
        return self._denominator

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:iir",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
