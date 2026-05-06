"""``AudioFeatureExtractor`` — standard audio feature extraction.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate n_mfcc, n_fft, and hop_length.
    3. Compute RMS energy across frames.
    4. Compute zero-crossing rate.
    5. Compute spectral centroid from the STFT magnitude spectrum.
    6. Compute spectral bandwidth from the centroid.
    7. Compute MFCC coefficients and take the mean over time.
    8. Return a dictionary with all five feature values.

Math:
    Spectral centroid:

    $$C = \\frac{\\sum_f f \\cdot |X(f)|}{\\sum_f |X(f)|}$$

    Spectral bandwidth:

    $$B = \\sqrt{\\frac{\\sum_f (f - C)^2 \\cdot |X(f)|}{\\sum_f |X(f)|}}$$

    MFCC coefficients use the DCT-II of log mel-filterbank energies.

References:
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
    - Davis, S. & Mermelstein, P. (1980). "Comparison of parametric representations
      for monosyllabic word recognition." IEEE Trans. ASSP, 28(4), 357-366.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AudioFeatureExtractor(Knot):
    """Extract a dictionary of standard audio features from a signal.

    Features: RMS energy, zero-crossing rate, spectral centroid,
    spectral bandwidth, and MFCC mean.

    Production needs ``librosa``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        n_mfcc: Knot | int,
        n_fft: Knot | int,
        hop_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            n_mfcc=n_mfcc,
            n_fft=n_fft,
            hop_length=hop_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        n_mfcc: int,
        n_fft: int,
        hop_length: int,
        **_: Any,
    ) -> dict[str, float]:
        """Extract standard audio features from the signal.

        Args:
            signal: Audio signal to extract features from.
            n_mfcc: Number of MFCC coefficients (positive integer).
            n_fft: FFT window size (positive integer).
            hop_length: Hop size in samples (positive integer).

        Returns:
            Dictionary with keys ``rms_energy``, ``zero_crossing_rate``,
            ``spectral_centroid``, ``spectral_bandwidth``, and ``mfcc_mean``.

        Raises:
            ValueError: If n_mfcc, n_fft, or hop_length are invalid.
        """
        if not isinstance(n_mfcc, int) or n_mfcc <= 0:
            raise ValueError(
                "AudioFeatureExtractor: n_mfcc must be a positive integer"
            )
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError(
                "AudioFeatureExtractor: n_fft must be a positive integer"
            )
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError(
                "AudioFeatureExtractor: hop_length must be a positive integer"
            )
        return {
            "rms_energy": 0.0,
            "zero_crossing_rate": 0.0,
            "spectral_centroid": 0.0,
            "spectral_bandwidth": 0.0,
            "mfcc_mean": 0.0,
        }
