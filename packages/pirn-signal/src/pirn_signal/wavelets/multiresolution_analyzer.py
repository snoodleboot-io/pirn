"""``MultiresolutionAnalyzer`` — Mallat-style multiresolution analysis.

Algorithm:
    1. Receive the input signal frame, wavelet_name, and level_count.
    2. Validate wavelet_name (non-empty string) and level_count (positive integer).
    3. Apply the Mallat algorithm: at each level, convolve the approximation
       subband with the low-pass filter and downsample by 2.
    4. Store the approximation and detail subbands for each level.
    5. Return a WaveletFrame with level_count decomposition levels.

Math:
    Multiresolution approximation at scale $j$:

    $$A_j f = \\sum_k \\langle f, \\phi_{j,k} \\rangle \\phi_{j,k}$$

    Detail subspace projection:

    $$D_j f = A_{j-1} f - A_j f = \\sum_k \\langle f, \\psi_{j,k} \\rangle \\psi_{j,k}$$

References:
    - Mallat, S. (1989). "Multiresolution approximations and wavelet orthonormal bases of $L^2(R)$."
      Trans. Am. Math. Soc., 315(1), 69-87.
    - pywt.mra: https://pywavelets.readthedocs.io/en/latest/ref/mra.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pywt
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload


def _run_mra(data: np.ndarray, wavelet_name: str, level: int) -> list[np.ndarray]:
    return list(pywt.wavedec(data, wavelet_name, level=level, axis=-1))


class MultiresolutionAnalyzer(Knot):
    """Mallat multiresolution decomposition."""

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet_name: Knot | str,
        level_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            wavelet_name=wavelet_name,
            level_count=level_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        wavelet_name: str,
        level_count: int,
        **_: Any,
    ) -> WaveletPayload:
        """Decompose the signal via Mallat multiresolution analysis and return a WaveletPayload.

        Args:
            signal: Signal payload to decompose.
            wavelet_name: Name of the wavelet (non-empty string).
            level_count: Number of decomposition levels (positive integer).

        Returns:
            WaveletPayload of multiresolution decomposition coefficient arrays.

        Raises:
            ValueError: If wavelet_name or level_count are invalid.
        """
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError("MultiresolutionAnalyzer: wavelet_name must be a non-empty string")
        if not isinstance(level_count, int) or level_count <= 0:
            raise ValueError("MultiresolutionAnalyzer: level_count must be a positive integer")
        coeffs = await asyncio.to_thread(_run_mra, signal.data, wavelet_name, level_count)
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name=wavelet_name,
            scale_count=len(coeffs),
        )
        return WaveletPayload(metadata=frame, data=coeffs)
