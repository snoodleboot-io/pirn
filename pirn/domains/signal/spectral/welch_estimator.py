"""``WelchEstimator`` — power spectral density via Welch's method."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class WelchEstimator(Knot):
    """Estimate PSD via averaged modified periodograms (Welch's method).

    Production needs ``scipy.signal.welch``; this stub validates the
    segmentation parameters and emits a :class:`SpectrumFrame` reference.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        segment_length: int,
        overlap: int = 0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError(
                "WelchEstimator: segment_length must be a positive integer"
            )
        if not isinstance(overlap, int) or overlap < 0:
            raise ValueError(
                "WelchEstimator: overlap must be a non-negative integer"
            )
        if overlap >= segment_length:
            raise ValueError(
                "WelchEstimator: overlap must be smaller than segment_length"
            )
        self._segment_length = segment_length
        self._overlap = overlap
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def segment_length(self) -> int:
        return self._segment_length

    @property
    def overlap(self) -> int:
        return self._overlap

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        """Estimate the PSD via Welch's averaged modified periodogram method and return a SpectrumFrame.

        Args:
            signal: Signal to estimate the power spectral density from via Welch's method.

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to half the segment length plus one.
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
