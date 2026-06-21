"""``EMDDecomposer`` — empirical mode decomposition.

Algorithm:
    1. Receive the input signal frame and max_imf_count.
    2. Validate max_imf_count (positive integer).
    3. Extract the first IMF via the sifting process:
       a. Identify all local extrema of the signal.
       b. Fit upper and lower envelopes via cubic spline interpolation.
       c. Subtract the mean envelope from the signal.
       d. Repeat until the result satisfies the IMF criteria.
    4. Subtract the extracted IMF from the signal and repeat for subsequent IMFs.
    5. Stop when fewer than two extrema remain or max_imf_count is reached.
    6. Return a WaveletFrame with max_imf_count IMF scales.

Math:
    IMF sifting criterion:

    $$|\\text{mean envelope}(t)| \\ll |h(t)| \\quad \\text{and}$$ the number of extrema and zero-crossings
    differ by at most one.

    Signal decomposition:

    $$x(t) = \\sum_{k=1}^{K} c_k(t) + r_K(t)$$

References:
    - Huang, N.E. et al. (1998). "The empirical mode decomposition and the Hilbert spectrum for nonlinear and
      non-stationary time series analysis." Proc. R. Soc. Lond. A, 454(1971), 903-995.
    - PyEMD: https://pyemd.readthedocs.io/
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from PyEMD import EMD

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload


def _emd_1d(channel: np.ndarray, max_imf: int) -> np.ndarray:
    emd = EMD()
    return emd.emd(channel, max_imf=max_imf)


def _run_emd(data: np.ndarray, max_imf: int) -> list[np.ndarray]:
    if data.ndim == 1:
        imfs = _emd_1d(data, max_imf)
        return [imfs[i] for i in range(len(imfs))]
    results: list[np.ndarray] = []
    for ch_idx in range(data.shape[0]):
        imfs = _emd_1d(data[ch_idx], max_imf)
        results.extend(imfs[i] for i in range(len(imfs)))
    return results


class EMDDecomposer(Knot):
    """Empirical mode decomposition into intrinsic mode functions."""

    def __init__(
        self,
        *,
        signal: Knot,
        max_imf_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            max_imf_count=max_imf_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        max_imf_count: int,
        **_: Any,
    ) -> WaveletPayload:
        """Decompose the signal into intrinsic mode functions via empirical mode decomposition.

        Args:
            signal: Signal payload to decompose.
            max_imf_count: Maximum number of IMFs to extract (positive integer).

        Returns:
            WaveletPayload of EMD intrinsic mode functions.

        Raises:
            ValueError: If max_imf_count is not a positive integer.
        """
        if not isinstance(max_imf_count, int) or max_imf_count <= 0:
            raise ValueError("EMDDecomposer: max_imf_count must be a positive integer")
        imfs = await asyncio.to_thread(_run_emd, signal.data, max_imf_count)
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name="emd",
            scale_count=len(imfs),
        )
        return WaveletPayload(metadata=frame, data=imfs)
