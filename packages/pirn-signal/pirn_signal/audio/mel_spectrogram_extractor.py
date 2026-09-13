"""``MelSpectrogramExtractor`` — mel-scaled spectrogram feature.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate n_mels, n_fft, and hop_length (hop_length must not exceed n_fft).
    3. Compute the STFT with window size n_fft and hop size hop_length.
    4. Square the magnitude spectrum to obtain the power spectrum.
    5. Apply a mel filterbank matrix M in R^{n_mels x (n_fft/2+1)} to obtain
       mel-band energies.
    6. Optionally convert to dB: S_mel_db = 10 log10(S_mel).
    7. Repeat independently for each channel and return a SpectrumPayload with
       frequency_bins = n_mels.

Math:
    Mel filterbank output:

    $$\\mathbf{S}_{\\text{mel}} = \\mathbf{M} \\cdot |\\text{STFT}(x)|^2$$

    Mel frequency scale conversion:

    $$m = 2595 \\log_{10}\\!\\left(1 + \\frac{f}{700}\\right)$$

    Frequency resolution: $\\Delta f = f_s / n_{\\text{fft}}$ Hz/bin.

References:
    - O'Shaughnessy, D. (1987). "Speech Communication: Human and Machine." Addison-Wesley.
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


class MelSpectrogramExtractor(Knot):
    """Compute a mel-spectrogram from an audio signal using ``librosa.feature.melspectrogram``."""

    def __init__(
        self,
        *,
        signal: Knot,
        n_mels: Knot | int,
        n_fft: Knot | int,
        hop_length: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            n_mels=n_mels,
            n_fft=n_fft,
            hop_length=hop_length,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        n_mels: int,
        n_fft: int,
        hop_length: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Compute a mel-spectrogram from the audio signal.

        Args:
            signal: Audio signal to compute the mel-spectrogram from.
            n_mels: Number of mel frequency bands (positive integer).
            n_fft: FFT window size (positive integer).
            hop_length: Hop size in samples (positive integer, must not exceed n_fft).

        Returns:
            SpectrumPayload with ``data`` shaped ``(channel_count, n_mels, n_frames)``.
            ``frequency_resolution_hz`` is ``0.0``: the mel scale is non-uniform in Hz.

        Raises:
            ValueError: If n_mels, n_fft, or hop_length are invalid.
        """
        if not isinstance(n_mels, int) or n_mels <= 0:
            raise ValueError("MelSpectrogramExtractor: n_mels must be a positive integer")
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError("MelSpectrogramExtractor: n_fft must be a positive integer")
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("MelSpectrogramExtractor: hop_length must be a positive integer")
        if hop_length > n_fft:
            raise ValueError("MelSpectrogramExtractor: hop_length must not exceed n_fft")
        sr = int(signal.frame.sample_rate_hz)
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    MelSpectrogramExtractor._compute_mel_spectrogram,
                    channel,
                    sr,
                    n_mels,
                    n_fft,
                    hop_length,
                )
                for channel in channels
            )
        )
        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=f"{signal.frame.signal_id}:mel-spectrogram",
                frequency_bins=n_mels,
                frequency_resolution_hz=0.0,
            ),
            data=np.stack(results, axis=0),
        )

    @staticmethod
    def _compute_mel_spectrogram(
        mono: np.ndarray, sr: int, n_mels: int, n_fft: int, hop_length: int
    ) -> np.ndarray:
        try:
            import librosa  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "MelSpectrogramExtractor requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        return librosa.feature.melspectrogram(
            y=mono, sr=sr, n_mels=n_mels, n_fft=n_fft, hop_length=hop_length
        )
