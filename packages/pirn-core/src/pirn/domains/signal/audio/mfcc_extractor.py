"""``MFCCExtractor`` — mel-frequency cepstral coefficients.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate n_mfcc, n_fft, and hop_length.
    3. Compute the mel-spectrogram with n_fft and hop_length.
    4. Take the log of mel-band energies (log-mel filterbank).
    5. Apply DCT-II to the log-mel energies to obtain n_mfcc cepstral coefficients.
    6. Return a SpectrumFrame with frequency_bins = n_mfcc.

Math:
    DCT-II for MFCCs:

    $$c_k = \\sum_{m=1}^{M} \\log E_m \\cos\\!\\left(\\frac{\\pi k}{M}\\left(m - \\frac{1}{2}\\right)\\right), \\quad k = 1, \\ldots, n_{\\text{mfcc}}$$

    where $E_m$ are the mel filterbank energies and $M$ is the number of mel bands.

References:
    - Davis, S. & Mermelstein, P. (1980). "Comparison of parametric representations
      for monosyllabic word recognition in continuously spoken sentences."
      IEEE Trans. ASSP, 28(4), 357-366.
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
"""

from __future__ import annotations

import asyncio
from typing import Any

import librosa
import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _compute_mfcc(
    mono: np.ndarray, sr: int, n_mfcc: int, n_fft: int, hop_length: int
) -> np.ndarray:
    return librosa.feature.mfcc(y=mono, sr=sr, n_mfcc=n_mfcc, n_fft=n_fft, hop_length=hop_length)


class MFCCExtractor(Knot):
    """Compute MFCC features from an audio signal using ``librosa.feature.mfcc``."""

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
        """Extract MFCC features from the audio signal.

        Args:
            signal: Audio signal to extract MFCC features from.
            n_mfcc: Number of MFCC coefficients (positive integer).
            n_fft: FFT window size (positive integer).
            hop_length: Hop size in samples (positive integer, must not exceed n_fft).

        Returns:
            Dictionary with ``mfcc`` (list of lists), ``n_mfcc``, and ``signal_id``.

        Raises:
            ValueError: If n_mfcc, n_fft, or hop_length are invalid.
        """
        if not isinstance(n_mfcc, int) or n_mfcc <= 0:
            raise ValueError("MFCCExtractor: n_mfcc must be a positive integer")
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError("MFCCExtractor: n_fft must be a positive integer")
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("MFCCExtractor: hop_length must be a positive integer")
        if hop_length > n_fft:
            raise ValueError("MFCCExtractor: hop_length must not exceed n_fft")
        mono = signal.data[0] if signal.data.ndim > 1 else signal.data
        sr = int(signal.frame.sample_rate_hz)
        mfcc = await asyncio.to_thread(_compute_mfcc, mono, sr, n_mfcc, n_fft, hop_length)
        return {
            "mfcc": mfcc.tolist(),
            "n_mfcc": n_mfcc,
            "signal_id": signal.frame.signal_id,
        }
