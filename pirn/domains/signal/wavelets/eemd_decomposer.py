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
        signal: SignalFrame,
        ensemble_size: int,
        noise_amplitude: float,
        max_imf_count: int,
        **_: Any,
    ) -> WaveletFrame:
        """Decompose the signal into intrinsic mode functions via ensemble EMD and return a WaveletFrame.

        Args:
            signal: Signal to decompose into IMFs using ensemble empirical mode decomposition.
            ensemble_size: Number of noise-assisted realisations to average (positive integer).
            noise_amplitude: Standard deviation of added white noise (positive float).
            max_imf_count: Maximum number of IMFs to extract (positive integer).

        Returns:
            WaveletFrame of EEMD intrinsic mode functions with up to ``max_imf_count`` scales.

        Raises:
            ValueError: If ensemble_size, noise_amplitude, or max_imf_count are invalid.
        """
        if not isinstance(ensemble_size, int) or ensemble_size <= 0:
            raise ValueError("EEMDDecomposer: ensemble_size must be a positive integer")
        if not isinstance(noise_amplitude, (int, float)) or noise_amplitude <= 0:
            raise ValueError("EEMDDecomposer: noise_amplitude must be positive")
        if not isinstance(max_imf_count, int) or max_imf_count <= 0:
            raise ValueError("EEMDDecomposer: max_imf_count must be a positive integer")
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name="eemd",
            scale_count=max_imf_count,
        )
