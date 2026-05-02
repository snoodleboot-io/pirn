"""``DWTDecomposer`` — discrete wavelet transform decomposition."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class DWTDecomposer(Knot):
    """Multi-level discrete wavelet transform.

    Production needs ``pywt.wavedec``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet_name: str,
        level_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError(
                "DWTDecomposer: wavelet_name must be a non-empty string"
            )
        if not isinstance(level_count, int) or level_count <= 0:
            raise ValueError(
                "DWTDecomposer: level_count must be a positive integer"
            )
        self._wavelet_name = wavelet_name
        self._level_count = level_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def wavelet_name(self) -> str:
        return self._wavelet_name

    @property
    def level_count(self) -> int:
        return self._level_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> WaveletFrame:
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name=self._wavelet_name,
            scale_count=self._level_count,
        )
