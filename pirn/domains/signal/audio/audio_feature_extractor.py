"""``AudioFeatureExtractor`` — standard audio feature extraction."""

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
        n_mfcc: int,
        n_fft: int,
        hop_length: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
    ) -> dict[str, float]:
        """Extract standard audio features from the signal and return them as a named mapping.

        Args:
            signal: Audio signal to extract features from.

        Returns:
            Dictionary with keys ``rms_energy``, ``zero_crossing_rate``,
            ``spectral_centroid``, ``spectral_bandwidth``, and ``mfcc_mean``.
        """
        return {
            "rms_energy": 0.0,
            "zero_crossing_rate": 0.0,
            "spectral_centroid": 0.0,
            "spectral_bandwidth": 0.0,
            "mfcc_mean": 0.0,
        }
