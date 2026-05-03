"""``BartlettPSDEstimator`` — Bartlett method PSD via averaged periodograms."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class BartlettPSDEstimator(Knot):
    """Estimate PSD via Bartlett's method: average non-overlapping periodograms."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_segments: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(num_segments, int) or num_segments <= 0:
            raise ValueError("BartlettPSDEstimator: num_segments must be a positive integer")
        self._num_segments = num_segments
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def num_segments(self) -> int:
        return self._num_segments

    async def process(self, signal: SignalFrame, **_: Any) -> SpectrumFrame:
        """Estimate the PSD via Bartlett's averaged periodogram method and return a SpectrumFrame.

        Args:
            signal: The input signal frame.

        Returns:
            SpectrumFrame with frequency_bins equal to half the per-segment sample count plus one.
        """
        segment_length = (
            signal.samples_per_channel // self._num_segments
            if self._num_segments > 0
            else signal.samples_per_channel
        )
        resolution = (
            signal.sample_rate_hz / segment_length
            if segment_length > 0 and signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=segment_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
