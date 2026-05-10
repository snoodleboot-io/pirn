"""``BispectrumAnalyzer`` — third-order spectral analysis via FFT outer product.

Algorithm:
    1. Receive the input signal payload and segment_length.
    2. Validate segment_length (positive integer).
    3. Compute X = np.fft.rfft(signal.data, n=segment_length, axis=-1).
    4. Compute bispectrum B = X[..., :, np.newaxis] * X[..., np.newaxis, :].
    5. Return a SpectrumPayload with 2D bispectrum and frequency_bins = segment_length // 2 + 1.

Math:
    Bispectrum:

    $$B(f_1, f_2) = X(f_1) \\cdot X(f_2)$$

References:
    - Nikias, C.L. & Raghuveer, M.R. (1987). "Bispectrum estimation: A digital signal processing
      framework." Proc. IEEE, 75(7), 869-891.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload


def _compute_bispectrum(data: np.ndarray, segment_length: int) -> np.ndarray:
    x = np.fft.rfft(data, n=segment_length, axis=-1)
    return x[..., :, np.newaxis] * x[..., np.newaxis, :]


class BispectrumAnalyzer(Knot):
    """Estimate the bispectrum via FFT outer product."""

    def __init__(
        self,
        *,
        signal: Knot,
        segment_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            segment_length=segment_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        segment_length: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Estimate the bispectrum from the signal and return a SpectrumPayload.

        Args:
            signal: Signal payload to compute the bispectrum from.
            segment_length: FFT size for bispectrum estimation (positive integer).

        Returns:
            SpectrumPayload with 2D bispectrum data and frequency_bins = segment_length // 2 + 1.

        Raises:
            ValueError: If segment_length is not a positive integer.
        """
        if not isinstance(segment_length, int) or segment_length <= 0:
            raise ValueError("BispectrumAnalyzer: segment_length must be a positive integer")

        bispectrum = await asyncio.to_thread(_compute_bispectrum, signal.data, segment_length)
        freq_bins = segment_length // 2 + 1
        freq_res = (
            signal.frame.sample_rate_hz / segment_length if signal.frame.sample_rate_hz > 0 else 0.0
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=freq_bins,
                frequency_resolution_hz=freq_res,
            ),
            data=bispectrum,
        )
