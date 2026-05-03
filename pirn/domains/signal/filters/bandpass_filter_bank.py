"""``BandpassFilterBank`` — apply N parallel bandpass filters."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BandpassFilterBank(Knot):
    """Apply a bank of parallel bandpass filters and return one SignalFrame per band."""

    def __init__(
        self,
        *,
        signal: Knot,
        bands: tuple[tuple[float, float], ...],
        order: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(bands, tuple) or len(bands) == 0:
            raise ValueError(
                "BandpassFilterBank: bands must be a non-empty tuple of (low_hz, high_hz) pairs"
            )
        for i, band in enumerate(bands):
            if (
                not isinstance(band, tuple)
                or len(band) != 2
                or not all(isinstance(v, (int, float)) for v in band)
            ):
                raise ValueError(
                    f"BandpassFilterBank: bands[{i}] must be a (low_hz, high_hz) tuple"
                )
            low, high = band
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError(
                    f"BandpassFilterBank: bands[{i}] must satisfy 0 < low_hz < high_hz"
                )
        if not isinstance(order, int) or order <= 0:
            raise ValueError("BandpassFilterBank: order must be a positive integer")
        self._bands = bands
        self._order = order
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def bands(self) -> tuple[tuple[float, float], ...]:
        return self._bands

    @property
    def order(self) -> int:
        return self._order

    async def process(self, signal: SignalFrame, **_: Any) -> list[SignalFrame]:
        """Apply parallel bandpass filters and return one SignalFrame per band.

        Args:
            signal: The input signal frame.

        Returns:
            List of SignalFrames, one per configured band.
        """
        return [
            SignalFrame(
                signal_id=f"{signal.signal_id}:bp-{i}",
                channel_count=signal.channel_count,
                sample_rate_hz=signal.sample_rate_hz,
                samples_per_channel=signal.samples_per_channel,
            )
            for i in range(len(self._bands))
        ]
