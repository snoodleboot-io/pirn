"""``ButterworthFilter`` — maximally-flat IIR filter (no passband ripple).

Production needs ``scipy.signal.butter`` plus ``scipy.signal.sosfiltfilt``
or equivalent. This stub validates the design parameters and threads a
:class:`SignalFrame` reference through with the same shape.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ButterworthFilter(Knot):
    """Configure and apply a Butterworth IIR filter."""

    def __init__(
        self,
        *,
        signal: Knot,
        order: int,
        cutoff_hz: float | tuple[float, float],
        band_type: str = "lowpass",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(order, int) or order <= 0:
            raise ValueError(
                "ButterworthFilter: order must be a positive integer"
            )
        if band_type not in {"lowpass", "highpass", "bandpass", "bandstop"}:
            raise ValueError(
                "ButterworthFilter: band_type must be one of "
                "'lowpass', 'highpass', 'bandpass', 'bandstop'"
            )
        self._validate_cutoff(cutoff_hz, band_type)
        self._order = order
        self._cutoff_hz = cutoff_hz
        self._band_type = band_type
        super().__init__(signal=signal, _config=_config, **kwargs)

    @staticmethod
    def _validate_cutoff(
        cutoff_hz: float | tuple[float, float], band_type: str
    ) -> None:
        if band_type in {"bandpass", "bandstop"}:
            if (
                not isinstance(cutoff_hz, tuple)
                or len(cutoff_hz) != 2
                or any(not isinstance(c, (int, float)) for c in cutoff_hz)
            ):
                raise ValueError(
                    "ButterworthFilter: bandpass/bandstop requires (low, high) tuple"
                )
            low, high = cutoff_hz
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError(
                    "ButterworthFilter: cutoff bounds must satisfy 0 < low < high"
                )
        else:
            if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
                raise ValueError(
                    "ButterworthFilter: cutoff_hz must be a positive scalar"
                )

    @property
    def order(self) -> int:
        return self._order

    @property
    def cutoff_hz(self) -> float | tuple[float, float]:
        return self._cutoff_hz

    @property
    def band_type(self) -> str:
        return self._band_type

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply the Butterworth IIR filter to the input signal and return the filtered SignalFrame.

        Args:
            signal: Signal to filter with a maximally-flat Butterworth design.

        Returns:
            SignalFrame filtered by the configured Butterworth IIR.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:butter-{self._band_type}",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
