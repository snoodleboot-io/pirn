"""``CWTDecomposer`` — continuous wavelet transform decomposition.

Algorithm:
    1. Receive the input signal frame, wavelet_name, and scale_count.
    2. Validate wavelet_name (non-empty string) and scale_count (positive integer).
    3. Generate a logarithmically spaced array of scale_count scales.
    4. For each scale, convolve the signal with the dilated/translated wavelet.
    5. Return a WaveletFrame with scale_count rows of CWT coefficients.

Math:
    CWT at scale $a$ and translation $b$:

    $$W_x(a, b) = \\frac{1}{\\sqrt{a}} \\int_{-\\infty}^{\\infty} x(t) \\psi^*\\!\\left(\\frac{t-b}{a}\\right) dt$$

    Reconstruction formula:

    $$x(t) = \\frac{1}{C_\\psi} \\int_0^\\infty \\int_{-\\infty}^\\infty W_x(a,b) \\psi_{a,b}(t) \\frac{db\\, da}{a^2}$$

References:
    - Mallat, S. (1999). "A Wavelet Tour of Signal Processing." Academic Press.
    - pywt.cwt: https://pywavelets.readthedocs.io/en/latest/ref/cwt.html
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


def _run_cwt(
    data: np.ndarray, wavelet_name: str, scale_count: int, sample_rate_hz: float
) -> list[np.ndarray]:
    scales = np.arange(1, scale_count + 1)
    sampling_period = 1.0 / sample_rate_hz if sample_rate_hz > 0 else 1.0
    coeffs, _freqs = pywt.cwt(data, scales, wavelet_name, sampling_period=sampling_period, axis=-1)
    return [coeffs[i] for i in range(len(scales))]


class CWTDecomposer(Knot):
    """Continuous wavelet transform."""

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet_name: Knot | str,
        scale_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            wavelet_name=wavelet_name,
            scale_count=scale_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        wavelet_name: str,
        scale_count: int,
        **_: Any,
    ) -> WaveletPayload:
        """Compute the continuous wavelet transform and return a WaveletPayload.

        Args:
            signal: Signal payload to decompose.
            wavelet_name: Name of the wavelet (non-empty string, e.g., ``cmor``, ``morl``).
            scale_count: Number of CWT scales (positive integer).

        Returns:
            WaveletPayload of CWT coefficient arrays, one per scale.

        Raises:
            ValueError: If wavelet_name or scale_count are invalid.
        """
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError("CWTDecomposer: wavelet_name must be a non-empty string")
        if not isinstance(scale_count, int) or scale_count <= 0:
            raise ValueError("CWTDecomposer: scale_count must be a positive integer")
        coeff_arrays = await asyncio.to_thread(
            _run_cwt, signal.data, wavelet_name, scale_count, signal.frame.sample_rate_hz
        )
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name=wavelet_name,
            scale_count=len(coeff_arrays),
        )
        return WaveletPayload(metadata=frame, data=coeff_arrays)
