"""``SWTDecomposer`` — stationary (undecimated) wavelet transform.

Algorithm:
    1. Receive the input signal frame, wavelet, and level.
    2. Validate wavelet (non-empty string) and level (positive integer).
    3. Apply the à-trous algorithm: at each level, convolve with the appropriately
       zero-inserted (upsampled) filter coefficients but do NOT downsample.
    4. All subbands retain the original signal length.
    5. Return a WaveletFrame with scale_count equal to level.

Math:
    SWT at level $j$ (à-trous filter):

    $$A_j[n] = \\sum_k h_{2^{j-1}}[k] A_{j-1}[n - 2^{j-1} k]$$

    where $h_{2^{j-1}}$ is the analysis filter upsampled by $2^{j-1}$.

References:
    - Shensa, M.J. (1992). "The discrete wavelet transform: wedding the à trous and Mallat algorithms."
      IEEE Trans. Signal Process., 40(10), 2464-2482.
    - pywt.swt: https://pywavelets.readthedocs.io/en/latest/ref/swt-stationary-wavelet-transform.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pywt

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.types.wavelet_payload import WaveletPayload


def _run_swt(data: np.ndarray, wavelet: str, level: int) -> list[np.ndarray]:
    pairs = pywt.swt(data, wavelet, level=level, axis=-1)
    return [c for pair in pairs for c in pair]


class SWTDecomposer(Knot):
    """Decompose a signal using the stationary (undecimated) wavelet transform."""

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet: Knot | str,
        level: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            wavelet=wavelet,
            level=level,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        wavelet: str,
        level: int,
        **_: Any,
    ) -> WaveletPayload:
        """Compute the stationary wavelet transform and return a WaveletPayload.

        Args:
            signal: The input signal payload.
            wavelet: Wavelet name (non-empty string).
            level: Number of decomposition levels (positive integer).

        Returns:
            WaveletPayload with 2*level coefficient arrays (cA, cD pairs flattened).

        Raises:
            ValueError: If wavelet or level are invalid.
        """
        if not isinstance(wavelet, str) or not wavelet:
            raise ValueError("SWTDecomposer: wavelet must be a non-empty string")
        if not isinstance(level, int) or level <= 0:
            raise ValueError("SWTDecomposer: level must be a positive integer")
        coeffs = await asyncio.to_thread(_run_swt, signal.data, wavelet, level)
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name=wavelet,
            scale_count=len(coeffs),
        )
        return WaveletPayload(metadata=frame, data=coeffs)
