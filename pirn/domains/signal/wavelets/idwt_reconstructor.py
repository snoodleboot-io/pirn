"""``IDWTReconstructor`` — inverse discrete wavelet transform."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class IDWTReconstructor(Knot):
    """Reconstruct a time-domain signal from a WaveletFrame via inverse DWT."""

    def __init__(
        self,
        *,
        wavelet_frame: Knot,
        wavelet: str,
        level: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(wavelet, str) or not wavelet:
            raise ValueError("IDWTReconstructor: wavelet must be a non-empty string")
        if not isinstance(level, int) or level <= 0:
            raise ValueError("IDWTReconstructor: level must be a positive integer")
        self._wavelet = wavelet
        self._level = level
        super().__init__(wavelet_frame=wavelet_frame, _config=_config, **kwargs)

    @property
    def wavelet(self) -> str:
        return self._wavelet

    @property
    def level(self) -> int:
        return self._level

    async def process(self, wavelet_frame: WaveletFrame, **_: Any) -> SignalFrame:
        """Reconstruct the time-domain signal from a WaveletFrame via inverse DWT.

        Args:
            wavelet_frame: The wavelet-domain representation to invert.

        Returns:
            SignalFrame containing the reconstructed signal.
        """
        return SignalFrame(
            signal_id=f"{wavelet_frame.signal_id}:idwt",
            channel_count=1,
            sample_rate_hz=0.0,
            samples_per_channel=wavelet_frame.scale_count * (2 ** self._level),
        )
