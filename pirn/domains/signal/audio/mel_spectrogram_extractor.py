"""``MelSpectrogramExtractor`` — mel-scaled spectrogram feature.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate n_mels, n_fft, and hop_length (hop_length must not exceed n_fft).
    3. Compute the STFT with window size n_fft and hop size hop_length.
    4. Square the magnitude spectrum to obtain the power spectrum.
    5. Apply a mel filterbank matrix M ∈ R^{n_mels × (n_fft/2+1)} to obtain
       mel-band energies.
    6. Optionally convert to dB: S_mel_db = 10 log10(S_mel).
    7. Return a SpectrumFrame with frequency_bins = n_mels.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class MelSpectrogramExtractor(Knot):
    """Compute a mel-spectrogram from an audio signal.

    Production needs ``librosa.feature.melspectrogram``.
    """

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
        signal: SignalFrame,
        n_mels: int,
        n_fft: int,
        hop_length: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Compute a mel-spectrogram from the audio signal.

        Args:
            signal: Audio signal to compute the mel-spectrogram from.
            n_mels: Number of mel frequency bands (positive integer).
            n_fft: FFT window size (positive integer).
            hop_length: Hop size in samples (positive integer, must not exceed n_fft).

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to ``n_mels`` and Hz-per-bin resolution.

        Raises:
            ValueError: If n_mels, n_fft, or hop_length are invalid.
        """
        if not isinstance(n_mels, int) or n_mels <= 0:
            raise ValueError(
                "MelSpectrogramExtractor: n_mels must be a positive integer"
            )
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError(
                "MelSpectrogramExtractor: n_fft must be a positive integer"
            )
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError(
                "MelSpectrogramExtractor: hop_length must be a positive integer"
            )
        if hop_length > n_fft:
            raise ValueError(
                "MelSpectrogramExtractor: hop_length must not exceed n_fft"
            )
        resolution = (
            signal.sample_rate_hz / n_fft
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=n_mels,
            frequency_resolution_hz=resolution,
        )
