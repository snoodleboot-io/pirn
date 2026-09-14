"""``AudioFeatureExtractor`` — standard audio feature extraction.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate n_mfcc, n_fft, and hop_length.
    3. Compute RMS energy across frames.
    4. Compute zero-crossing rate.
    5. Compute spectral centroid from the STFT magnitude spectrum.
    6. Compute spectral bandwidth from the centroid.
    7. Compute spectral rolloff.
    8. Repeat independently for each channel and return a FeaturePayload with
       all five per-frame feature curves per channel.

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
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class AudioFeatureExtractor(Knot):
    """Extract standard audio features from a signal.

    Features: RMS energy, zero-crossing rate, spectral centroid,
    spectral bandwidth, and spectral rolloff.
    """

    _feature_names: ClassVar[tuple[str, ...]] = (
        "rms_energy",
        "zero_crossing_rate",
        "spectral_centroid",
        "spectral_bandwidth",
        "spectral_rolloff",
    )

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
    ) -> FeaturePayload:
        """Extract standard audio features from the signal.

        Args:
            signal: Audio signal to extract features from.
            n_mfcc: Number of MFCC coefficients (positive integer, reserved for future use).
            n_fft: FFT window size (positive integer).
            hop_length: Hop size in samples (positive integer).

        Returns:
            FeaturePayload with ``data`` shaped ``(channel_count, 5, n_frames)`` — one
            curve per channel for each of ``rms_energy``, ``zero_crossing_rate``,
            ``spectral_centroid``, ``spectral_bandwidth``, and ``spectral_rolloff``.

        Raises:
            ValueError: If n_mfcc, n_fft, or hop_length are invalid.
        """
        if not isinstance(n_mfcc, int) or n_mfcc <= 0:
            raise ValueError("AudioFeatureExtractor: n_mfcc must be a positive integer")
        if not isinstance(n_fft, int) or n_fft <= 0:
            raise ValueError("AudioFeatureExtractor: n_fft must be a positive integer")
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("AudioFeatureExtractor: hop_length must be a positive integer")
        sr = int(signal.metadata.sample_rate_hz)
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    AudioFeatureExtractor._extract_features, channel, sr, n_fft, hop_length
                )
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:audio-features",
                channel_count=channels.shape[0],
                feature_names=AudioFeatureExtractor._feature_names,
            ),
            data=np.stack(results, axis=0),
        )

    @staticmethod
    def _extract_features(mono: np.ndarray, sr: int, n_fft: int, hop_length: int) -> np.ndarray:
        """Compute the five feature curves for a single channel, stacked as (5, n_frames)."""
        librosa = OptionalDependency.require("librosa", extra="signal", package="pirn-signal")
        rms = librosa.feature.rms(y=mono, frame_length=n_fft, hop_length=hop_length)
        zcr = librosa.feature.zero_crossing_rate(mono, frame_length=n_fft, hop_length=hop_length)
        centroid = librosa.feature.spectral_centroid(
            y=mono, sr=sr, n_fft=n_fft, hop_length=hop_length
        )
        bandwidth = librosa.feature.spectral_bandwidth(
            y=mono, sr=sr, n_fft=n_fft, hop_length=hop_length
        )
        rolloff = librosa.feature.spectral_rolloff(
            y=mono, sr=sr, n_fft=n_fft, hop_length=hop_length
        )
        return np.stack([rms[0], zcr[0], centroid[0], bandwidth[0], rolloff[0]], axis=0)
