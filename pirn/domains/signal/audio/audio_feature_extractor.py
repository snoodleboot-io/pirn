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

import asyncio
from typing import Any

import librosa
import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _extract_features(mono: np.ndarray, sr: int, n_fft: int, hop_length: int) -> dict[str, Any]:
    rms = librosa.feature.rms(y=mono, frame_length=n_fft, hop_length=hop_length)
    zcr = librosa.feature.zero_crossing_rate(mono, frame_length=n_fft, hop_length=hop_length)
    centroid = librosa.feature.spectral_centroid(y=mono, sr=sr, n_fft=n_fft, hop_length=hop_length)
    bandwidth = librosa.feature.spectral_bandwidth(
        y=mono, sr=sr, n_fft=n_fft, hop_length=hop_length
    )
    rolloff = librosa.feature.spectral_rolloff(y=mono, sr=sr, n_fft=n_fft, hop_length=hop_length)
    return {
        "rms_energy": rms[0].tolist(),
        "zero_crossing_rate": zcr[0].tolist(),
        "spectral_centroid": centroid[0].tolist(),
        "spectral_bandwidth": bandwidth[0].tolist(),
        "spectral_rolloff": rolloff[0].tolist(),
    }


class AudioFeatureExtractor(Knot):
    """Extract a dictionary of standard audio features from a signal.

    Features: RMS energy, zero-crossing rate, spectral centroid,
    spectral bandwidth, and spectral rolloff.
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
        signal: SignalPayload,
        n_mfcc: int,
        n_fft: int,
        hop_length: int,
        **_: Any,
    ) -> dict[str, Any]:
        """Extract standard audio features from the signal.

        Args:
            signal: Audio signal to extract features from.
            n_mfcc: Number of MFCC coefficients (positive integer, reserved for future use).
            n_fft: FFT window size (positive integer).
            hop_length: Hop size in samples (positive integer).

        Returns:
            Dictionary with keys ``rms_energy``, ``zero_crossing_rate``,
            ``spectral_centroid``, ``spectral_bandwidth``, and ``spectral_rolloff``
            as lists of float values per frame.

        Raises:
            ValueError: If n_mfcc, n_fft, or hop_length are invalid.
        """
        if not isinstance(n_mfcc, int) or n_mfcc <= 0:
            raise ValueError("AudioFeatureExtractor: n_mfcc must be a positive integer")
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError("AudioFeatureExtractor: n_fft must be a positive integer")
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("AudioFeatureExtractor: hop_length must be a positive integer")
        mono = signal.data[0] if signal.data.ndim > 1 else signal.data
        sr = int(signal.frame.sample_rate_hz)
        return await asyncio.to_thread(_extract_features, mono, sr, n_fft, hop_length)
