"""``MFCCExtractor`` — mel-frequency cepstral coefficients."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class MFCCExtractor(Knot):
    """Compute MFCC features from an audio signal.

    Production needs ``librosa.feature.mfcc``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        n_mfcc: int,
        n_fft: int,
        hop_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(n_mfcc, int) or n_mfcc <= 0:
            raise ValueError(
                "MFCCExtractor: n_mfcc must be a positive integer"
            )
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError(
                "MFCCExtractor: n_fft must be a positive integer"
            )
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError(
                "MFCCExtractor: hop_length must be a positive integer"
            )
        if hop_length > n_fft:
            raise ValueError(
                "MFCCExtractor: hop_length must not exceed n_fft"
            )
        self._n_mfcc = n_mfcc
        self._n_fft = n_fft
        self._hop_length = hop_length
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def n_mfcc(self) -> int:
        return self._n_mfcc

    @property
    def n_fft(self) -> int:
        return self._n_fft

    @property
    def hop_length(self) -> int:
        return self._hop_length

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SpectrumFrame:
        """Extract MFCC features from the audio signal and return a SpectrumFrame with n_mfcc coefficient bins.

        Args:
            signal: Audio signal to extract MFCC features from.

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to ``n_mfcc``.
        """
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=self._n_mfcc,
            frequency_resolution_hz=0.0,
        )
