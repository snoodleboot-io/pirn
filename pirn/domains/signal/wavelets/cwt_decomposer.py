"""``CWTDecomposer`` — continuous wavelet transform decomposition."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class CWTDecomposer(Knot):
    """Continuous wavelet transform.

    Production needs ``pywt.cwt`` or ``scipy.signal.cwt``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet_name: str,
        scale_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError(
                "CWTDecomposer: wavelet_name must be a non-empty string"
            )
        if not isinstance(scale_count, int) or scale_count <= 0:
            raise ValueError(
                "CWTDecomposer: scale_count must be a positive integer"
            )
        self._wavelet_name = wavelet_name
        self._scale_count = scale_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def wavelet_name(self) -> str:
        return self._wavelet_name

    @property
    def scale_count(self) -> int:
        return self._scale_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> WaveletFrame:
        """Compute the continuous wavelet transform of the signal and return a WaveletFrame.

        Args:
            signal: Signal to decompose using the configured wavelet at the configured scale count.

        Returns:
            WaveletFrame of CWT coefficients with ``scale_count`` scales.
        """
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name=self._wavelet_name,
            scale_count=self._scale_count,
        )
