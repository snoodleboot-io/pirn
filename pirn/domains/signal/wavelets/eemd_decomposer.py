"""``EEMDDecomposer`` — ensemble empirical mode decomposition."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class EEMDDecomposer(Knot):
    """Ensemble EMD with white-noise-assisted realisations.

    Production needs ``EMD-signal`` (PyEMD).
    """

    def __init__(
        self,
        *,
        signal: Knot,
        ensemble_size: int,
        noise_amplitude: float,
        max_imf_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(ensemble_size, int) or ensemble_size <= 0:
            raise ValueError(
                "EEMDDecomposer: ensemble_size must be a positive integer"
            )
        if not isinstance(noise_amplitude, (int, float)) or noise_amplitude <= 0:
            raise ValueError(
                "EEMDDecomposer: noise_amplitude must be positive"
            )
        if not isinstance(max_imf_count, int) or max_imf_count <= 0:
            raise ValueError(
                "EEMDDecomposer: max_imf_count must be a positive integer"
            )
        self._ensemble_size = ensemble_size
        self._noise_amplitude = float(noise_amplitude)
        self._max_imf_count = max_imf_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def ensemble_size(self) -> int:
        return self._ensemble_size

    @property
    def noise_amplitude(self) -> float:
        return self._noise_amplitude

    @property
    def max_imf_count(self) -> int:
        return self._max_imf_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> WaveletFrame:
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name="eemd",
            scale_count=self._max_imf_count,
        )
