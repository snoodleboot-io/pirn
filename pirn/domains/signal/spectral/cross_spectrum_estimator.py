"""``CrossSpectrumEstimator`` — cross-spectral density between two signals."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class CrossSpectrumEstimator(Knot):
    """Estimate the cross-spectral density between two signals.

    Production needs ``scipy.signal.csd``.
    """

    def __init__(
        self,
        *,
        signal_a: Knot,
        signal_b: Knot,
        segment_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError(
                "CrossSpectrumEstimator: segment_length must be a positive integer"
            )
        self._segment_length = segment_length
        super().__init__(
            signal_a=signal_a, signal_b=signal_b, _config=_config, **kwargs
        )

    @property
    def segment_length(self) -> int:
        return self._segment_length

    async def process(
        self,
        signal_a: SignalFrame,
        signal_b: SignalFrame,
        **_: Any,
    ) -> SpectrumFrame:
        """Estimate the cross-spectral density between two signals and return a SpectrumFrame.

        Args:
            signal_a: First signal for the cross-spectral density estimate.
            signal_b: Second signal for the cross-spectral density estimate.

        Returns:
            SpectrumFrame with bins equal to half the segment length plus one.

        Raises:
            ValueError: If signal_a and signal_b have different sample rates.
        """
        if signal_a.sample_rate_hz != signal_b.sample_rate_hz:
            raise ValueError(
                "CrossSpectrumEstimator: signal_a and signal_b must share a sample rate"
            )
        resolution = (
            signal_a.sample_rate_hz / self._segment_length
            if signal_a.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=f"{signal_a.signal_id}|{signal_b.signal_id}",
            frequency_bins=self._segment_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
