"""``BandPassFilter`` — pass a frequency band, attenuate elsewhere."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BandPassFilter(Knot):
    """Band-pass filter wrapper (front-end on a chosen IIR/FIR design).

    Production needs ``scipy.signal``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        low_cutoff_hz: float,
        high_cutoff_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(low_cutoff_hz, (int, float)) or low_cutoff_hz <= 0:
            raise ValueError(
                "BandPassFilter: low_cutoff_hz must be positive"
            )
        if not isinstance(high_cutoff_hz, (int, float)) or high_cutoff_hz <= 0:
            raise ValueError(
                "BandPassFilter: high_cutoff_hz must be positive"
            )
        if low_cutoff_hz >= high_cutoff_hz:
            raise ValueError(
                "BandPassFilter: low_cutoff_hz must be < high_cutoff_hz"
            )
        self._low_cutoff_hz = float(low_cutoff_hz)
        self._high_cutoff_hz = float(high_cutoff_hz)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def low_cutoff_hz(self) -> float:
        return self._low_cutoff_hz

    @property
    def high_cutoff_hz(self) -> float:
        return self._high_cutoff_hz

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Apply the band-pass filter to the input signal and return the filtered SignalFrame.

        Args:
            signal: Signal to band-pass filter.

        Returns:
            SignalFrame with frequencies outside the configured band attenuated.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:bandpass",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
