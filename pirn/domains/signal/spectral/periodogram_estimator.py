"""``PeriodogramEstimator`` — classical periodogram (squared FFT magnitude)."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class PeriodogramEstimator(Knot):
    """Single-block periodogram PSD estimator.

    Production needs ``scipy.signal.periodogram``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        window: str = "hann",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(window, str) or not window:
            raise ValueError(
                "PeriodogramEstimator: window must be a non-empty string"
            )
        self._window = window
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def window(self) -> str:
        return self._window

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        """Estimate the single-block periodogram PSD and return a SpectrumFrame.

        Args:
            signal: Signal to compute the classical periodogram power spectral density from.

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
