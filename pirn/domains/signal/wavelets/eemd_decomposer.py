"""``EEMDDecomposer`` — ensemble empirical mode decomposition.

Algorithm:
    1. Receive the input signal frame, ensemble_size, noise_amplitude, and max_imf_count.
    2. Validate ensemble_size and max_imf_count (positive integers) and
       noise_amplitude (positive float).
    3. For each of ensemble_size trials, add scaled white Gaussian noise to the signal.
    4. Apply EMD to each noisy realisation, extracting up to max_imf_count IMFs.
    5. Ensemble-average the IMFs across all realisations to cancel noise.
    6. Return a WaveletFrame with max_imf_count IMF scales.

Math:
    Ensemble average IMF:

    $$\\hat{c}_k(t) = \\frac{1}{N_e} \\sum_{i=1}^{N_e} c_k^{(i)}(t)$$

    where $c_k^{(i)}$ = $k$-th IMF from the $i$-th noisy realisation.

    Added noise:

    $$x^{(i)}(t) = x(t) + \\varepsilon n^{(i)}(t), \\quad \\varepsilon = \\text{noise\\_amplitude}$$

References:
    - Wu, Z. & Huang, N.E. (2009). "Ensemble empirical mode decomposition: a noise-assisted data
      analysis method." Adv. Adapt. Data Anal., 1(1), 1-41.
    - PyEMD: https://pyemd.readthedocs.io/
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from PyEMD import EEMD

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.types.wavelet_payload import WaveletPayload


def _eemd_1d(channel: np.ndarray, trials: int, noise_width: float, max_imf: int) -> np.ndarray:
    eemd = EEMD(trials=trials, noise_width=noise_width)
    return eemd.eemd(channel, max_imf=max_imf)


def _run_eemd(
    data: np.ndarray, ensemble_size: int, noise_amplitude: float, max_imf: int
) -> list[np.ndarray]:
    if data.ndim == 1:
        imfs = _eemd_1d(data, ensemble_size, noise_amplitude, max_imf)
        return [imfs[i] for i in range(len(imfs))]
    results: list[np.ndarray] = []
    for ch_idx in range(data.shape[0]):
        imfs = _eemd_1d(data[ch_idx], ensemble_size, noise_amplitude, max_imf)
        results.extend(imfs[i] for i in range(len(imfs)))
    return results


class EEMDDecomposer(Knot):
    """Ensemble EMD with white-noise-assisted realisations."""

    def __init__(
        self,
        *,
        signal: Knot,
        ensemble_size: Knot | int,
        noise_amplitude: Knot | float,
        max_imf_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            ensemble_size=ensemble_size,
            noise_amplitude=noise_amplitude,
            max_imf_count=max_imf_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        ensemble_size: int,
        noise_amplitude: float,
        max_imf_count: int,
        **_: Any,
    ) -> WaveletPayload:
        """Decompose the signal into intrinsic mode functions via ensemble EMD.

        Args:
            signal: Signal payload to decompose.
            ensemble_size: Number of noise-assisted realisations to average (positive integer).
            noise_amplitude: Standard deviation of added white noise (positive float).
            max_imf_count: Maximum number of IMFs to extract (positive integer).

        Returns:
            WaveletPayload of EEMD intrinsic mode functions.

        Raises:
            ValueError: If ensemble_size, noise_amplitude, or max_imf_count are invalid.
        """
        if not isinstance(ensemble_size, int) or ensemble_size <= 0:
            raise ValueError("EEMDDecomposer: ensemble_size must be a positive integer")
        if not isinstance(noise_amplitude, (int, float)) or noise_amplitude <= 0:
            raise ValueError("EEMDDecomposer: noise_amplitude must be positive")
        if not isinstance(max_imf_count, int) or max_imf_count <= 0:
            raise ValueError("EEMDDecomposer: max_imf_count must be a positive integer")
        imfs = await asyncio.to_thread(
            _run_eemd, signal.data, ensemble_size, noise_amplitude, max_imf_count
        )
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name="eemd",
            scale_count=len(imfs),
        )
        return WaveletPayload(metadata=frame, data=imfs)
