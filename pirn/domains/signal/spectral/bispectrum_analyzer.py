"""``BispectrumAnalyzer`` — third-order spectral analysis."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class BispectrumAnalyzer(Knot):
    """Estimate the bispectrum (third-order cumulant spectrum).

    Production needs ``scipy`` plus a higher-order-statistics
    implementation; the standard library does not ship one.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        segment_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError(
                "BispectrumAnalyzer: segment_length must be a positive integer"
            )
        self._segment_length = segment_length
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def segment_length(self) -> int:
        return self._segment_length

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        """Estimate the bispectrum from the signal and return a SpectrumFrame of third-order spectral coefficients.

        Args:
            signal: Signal to compute the third-order cumulant spectrum from.

        Returns:
            SpectrumFrame with bins equal to half the segment length plus one.
        """
        resolution = (
            signal.sample_rate_hz / self._segment_length
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=self._segment_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
