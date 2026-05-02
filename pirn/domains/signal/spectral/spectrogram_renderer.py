"""``SpectrogramRenderer`` — render a spectrogram from a STFT/PSD."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class SpectrogramRenderer(Knot):
    """Build a magnitude spectrogram from a windowed STFT.

    Production needs ``scipy.signal.spectrogram``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        window_length: int,
        scaling: str = "density",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError(
                "SpectrogramRenderer: window_length must be a positive integer"
            )
        if scaling not in {"density", "spectrum"}:
            raise ValueError(
                "SpectrogramRenderer: scaling must be 'density' or 'spectrum'"
            )
        self._window_length = window_length
        self._scaling = scaling
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def window_length(self) -> int:
        return self._window_length

    @property
    def scaling(self) -> str:
        return self._scaling

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        resolution = (
            signal.sample_rate_hz / self._window_length
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=self._window_length // 2 + 1,
            frequency_resolution_hz=resolution,
        )
