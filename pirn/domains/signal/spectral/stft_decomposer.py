"""``STFTDecomposer`` — short-time Fourier transform."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class STFTDecomposer(Knot):
    """Sliding-window FFT producing a time-frequency representation.

    Production needs ``scipy.signal.stft``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        window_length: int,
        hop_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(window_length, int) or window_length <= 0:
            raise ValueError(
                "STFTDecomposer: window_length must be a positive integer"
            )
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError(
                "STFTDecomposer: hop_length must be a positive integer"
            )
        if hop_length > window_length:
            raise ValueError(
                "STFTDecomposer: hop_length must not exceed window_length"
            )
        self._window_length = window_length
        self._hop_length = hop_length
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def window_length(self) -> int:
        return self._window_length

    @property
    def hop_length(self) -> int:
        return self._hop_length

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
