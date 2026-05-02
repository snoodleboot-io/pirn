"""``EMDDecomposer`` — empirical mode decomposition."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class EMDDecomposer(Knot):
    """Empirical mode decomposition into intrinsic mode functions.

    Production needs ``EMD-signal`` (PyEMD) or similar.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        max_imf_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(max_imf_count, int) or max_imf_count <= 0:
            raise ValueError(
                "EMDDecomposer: max_imf_count must be a positive integer"
            )
        self._max_imf_count = max_imf_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def max_imf_count(self) -> int:
        return self._max_imf_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> WaveletFrame:
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name="emd",
            scale_count=self._max_imf_count,
        )
