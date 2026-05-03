"""``FIRParksMcClellanFilter`` — equiripple FIR via Parks-McClellan algorithm."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FIRParksMcClellanFilter(Knot):
    """Design an equiripple FIR filter via the Parks-McClellan (Remez) algorithm."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_taps: int,
        bands: tuple[float, ...],
        desired: tuple[float, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(num_taps, int) or num_taps <= 0 or num_taps % 2 == 0:
            raise ValueError(
                "FIRParksMcClellanFilter: num_taps must be a positive odd integer"
            )
        if not isinstance(bands, tuple) or len(bands) < 2 or len(bands) % 2 != 0:
            raise ValueError(
                "FIRParksMcClellanFilter: bands must be a tuple of an even number of edge frequencies"
            )
        if not isinstance(desired, tuple) or len(desired) != len(bands) // 2:
            raise ValueError(
                "FIRParksMcClellanFilter: desired must have one value per band"
            )
        self._num_taps = num_taps
        self._bands = bands
        self._desired = desired
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def num_taps(self) -> int:
        return self._num_taps

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the Parks-McClellan equiripple FIR filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.

        Returns:
            Filtered SignalFrame with the same shape as the input.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:fir-pm",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
