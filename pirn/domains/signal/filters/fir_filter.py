"""``FIRFilter`` — finite impulse response filter."""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FIRFilter(Knot):
    """Apply a pre-designed FIR coefficient set.

    Production needs ``scipy.signal.lfilter`` / ``firwin`` for design.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        coefficients: Sequence[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        coeffs = tuple(coefficients)
        if not coeffs:
            raise ValueError("FIRFilter: coefficients must be non-empty")
        for c in coeffs:
            if not isinstance(c, (int, float)):
                raise TypeError(
                    "FIRFilter: every coefficient must be a real number"
                )
        self._coefficients = tuple(float(c) for c in coeffs)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def coefficients(self) -> tuple[float, ...]:
        return self._coefficients

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Convolve the configured FIR coefficients with the input signal and return the filtered SignalFrame.

        Args:
            signal: Signal to convolve with the FIR tap coefficients.

        Returns:
            SignalFrame of the FIR-filtered output.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:fir",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
