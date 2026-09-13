"""``MFCCExtractor`` — mel-frequency cepstral coefficients.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate n_mfcc, n_fft, and hop_length.
    3. Compute the mel-spectrogram with n_fft and hop_length.
    4. Take the log of mel-band energies (log-mel filterbank).
    5. Apply DCT-II to the log-mel energies to obtain n_mfcc cepstral coefficients.
    6. Repeat independently for each channel and return a SpectrumPayload with
       frequency_bins = n_mfcc.

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

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


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
    ) -> SpectrumPayload:
        """Extract MFCC features from the audio signal.

        Args:
            signal: Audio signal to extract MFCC features from.
            n_mfcc: Number of MFCC coefficients (positive integer).
            n_fft: FFT window size (positive integer).
            hop_length: Hop size in samples (positive integer, must not exceed n_fft).

        Returns:
            SpectrumPayload with ``data`` shaped ``(channel_count, n_mfcc, n_frames)``.
            ``frequency_resolution_hz`` is ``0.0``: the cepstral coefficient axis is
            not a uniform frequency axis.

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
        sr = int(signal.frame.sample_rate_hz)
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    MFCCExtractor._compute_mfcc, channel, sr, n_mfcc, n_fft, hop_length
                )
                for channel in channels
            )
        )
        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=f"{signal.frame.signal_id}:mfcc",
                frequency_bins=n_mfcc,
                frequency_resolution_hz=0.0,
            ),
            data=np.stack(results, axis=0),
        )

    @staticmethod
    def _compute_mfcc(
        mono: np.ndarray, sr: int, n_mfcc: int, n_fft: int, hop_length: int
    ) -> np.ndarray:
        try:
            import librosa  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "MFCCExtractor requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        return librosa.feature.mfcc(
            y=mono, sr=sr, n_mfcc=n_mfcc, n_fft=n_fft, hop_length=hop_length
        )
