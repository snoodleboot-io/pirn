"""``MelSpectrogramExtractor`` — mel-scaled spectrogram feature."""

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
        n_mels: int,
        n_fft: int,
        hop_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._n_mels = n_mels
        self._n_fft = n_fft
        self._hop_length = hop_length
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def n_mels(self) -> int:
        return self._n_mels

    @property
    def n_fft(self) -> int:
        return self._n_fft

    @property
    def hop_length(self) -> int:
        return self._hop_length

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        """Compute a mel-spectrogram from the audio signal and return a SpectrumFrame with mel-bin resolution.

        Args:
            signal: Audio signal to compute the mel-spectrogram from.

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to ``n_mels`` and Hz-per-bin resolution.
        """
        resolution = (
            signal.sample_rate_hz / self._n_fft
            if signal.sample_rate_hz > 0
            else 0.0
        )
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=self._n_mels,
            frequency_resolution_hz=resolution,
        )
