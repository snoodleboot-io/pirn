"""``FFTAnalyzer`` — emit a :class:`SpectrumFrame` reference for a signal.

Production deployments install ``scipy`` (``scipy.fft`` / ``numpy.fft``)
and substitute a concrete implementation that fills in the spectrum
samples. This stub focuses on shape/lineage validation so the rest of
the orchestration graph can be built and tested without the heavy DSP
dependency.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class FFTAnalyzer(Knot):
    """Forward FFT of a single-channel signal."""

    def __init__(
        self,
        *,
        signal: Knot,
        n_fft: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError("FFTAnalyzer: n_fft must be a positive integer")
        if n_fft & (n_fft - 1) != 0:
            raise ValueError(
                "FFTAnalyzer: n_fft must be a power of two for radix-2 FFT"
            )
        self._n_fft = n_fft
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def n_fft(self) -> int:
        return self._n_fft

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        resolution = (
            signal.sample_rate_hz / self._n_fft
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=self._n_fft // 2 + 1,
            frequency_resolution_hz=resolution,
        )
