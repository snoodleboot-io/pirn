"""``MultitaperEstimator`` — Slepian-taper PSD with low spectral leakage."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class MultitaperEstimator(Knot):
    """Multitaper PSD via discrete prolate spheroidal sequences (DPSS).

    Production needs ``scipy.signal.windows.dpss`` plus a multitaper
    averaging routine.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        time_bandwidth: float,
        taper_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(time_bandwidth, (int, float)) or time_bandwidth <= 0:
            raise ValueError(
                "MultitaperEstimator: time_bandwidth must be positive"
            )
        if not isinstance(taper_count, int) or taper_count <= 0:
            raise ValueError(
                "MultitaperEstimator: taper_count must be a positive integer"
            )
        self._time_bandwidth = float(time_bandwidth)
        self._taper_count = taper_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def time_bandwidth(self) -> float:
        return self._time_bandwidth

    @property
    def taper_count(self) -> int:
        return self._taper_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        """Estimate the PSD via Slepian-taper averaging and return a SpectrumFrame.

        Args:
            signal: Signal to estimate the multitaper power spectral density from.

        Returns:
            SpectrumFrame with bins equal to half the sample count plus one.
        """
        n = max(signal.samples_per_channel, 1)
        resolution = (
            signal.sample_rate_hz / n
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=n // 2 + 1,
            frequency_resolution_hz=resolution,
        )
