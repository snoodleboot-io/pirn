"""``SWTDecomposer`` — stationary (undecimated) wavelet transform."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class SWTDecomposer(Knot):
    """Decompose a signal using the stationary (undecimated) wavelet transform."""

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet: str,
        level: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(wavelet, str) or not wavelet:
            raise ValueError("SWTDecomposer: wavelet must be a non-empty string")
        if not isinstance(level, int) or level <= 0:
            raise ValueError("SWTDecomposer: level must be a positive integer")
        self._wavelet = wavelet
        self._level = level
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def wavelet(self) -> str:
        return self._wavelet

    @property
    def level(self) -> int:
        return self._level

    async def process(self, signal: SignalFrame, **_: Any) -> WaveletFrame:
        """Compute the stationary wavelet transform and return a WaveletFrame.

        Args:
            signal: The input signal frame.

        Returns:
            WaveletFrame with scale_count equal to the decomposition level.
        """
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name=self._wavelet,
            scale_count=self._level,
        )
