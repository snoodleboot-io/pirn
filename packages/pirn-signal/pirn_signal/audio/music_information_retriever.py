"""``MusicInformationRetriever`` — high-level MIR feature aggregator.

Algorithm:
    1. Receive the input audio signal frame and feature_set.
    2. Validate that feature_set is a non-empty tuple of known feature names.
    3. For each requested feature:
       - chroma: compute chroma short-time energy (12-bin pitch class profile).
       - tempo: estimate BPM via beat tracker autocorrelation.
       - key: estimate musical key using chroma profile correlation with key templates.
       - structure: segment boundaries via novelty-based structural analysis.
       - harmonic: separate harmonic component via median filtering in STFT domain.
       - percussive: separate percussive component via median filtering in STFT domain.
    4. Repeat independently for each channel and return a FeaturePayload whose
       object-dtype ``data`` holds the (heterogeneously shaped) computed value
       for each requested feature, per channel.

Math:
    Key estimation correlates the mean chroma vector against the 12 pitch classes
    and picks the strongest:

    $$\\hat{k} = \\arg\\max_{p \\in \\{0, \\ldots, 11\\}} \\overline{C}_p, \\quad
    \\overline{C}_p = \\frac{1}{T} \\sum_{t=1}^{T} C_{p,t}$$

    where $C$ is the chroma-CQT matrix (12 pitch classes x $T$ frames). The
    remaining features (chroma, spectral contrast, tonnetz, tempo, harmonic/percussive
    separation, structure) delegate to ``librosa``; their formulae are defined within
    those routines.

References:
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
    - Müller, M. (2015). "Fundamentals of Music Processing." Springer.
"""

from __future__ import annotations

from functools import partial
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_signal._channel_fan_out import ChannelFanOut
from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class MusicInformationRetriever(Knot):
    """Aggregate MIR features using ``librosa``.

    Supported features: ``chroma``, ``spectral_contrast``, ``tonnetz``,
    ``tempo``, ``key``, ``harmonic``, ``percussive``, ``structure``.
    """

    _allowed_features: ClassVar[frozenset[str]] = frozenset(
        {
            "chroma",
            "tempo",
            "key",
            "structure",
            "harmonic",
            "percussive",
            "spectral_contrast",
            "tonnetz",
        }
    )

    def __init__(
        self,
        *,
        signal: Knot,
        feature_set: Knot | tuple[str, ...] = ("chroma", "tempo", "key"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            feature_set=feature_set,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        feature_set: tuple[str, ...] = ("chroma", "tempo", "key"),
        **_: Any,
    ) -> FeaturePayload:
        """Extract the configured MIR feature set from the audio signal.

        Args:
            signal: Audio signal to extract MIR features from.
            feature_set: Non-empty tuple of feature names to compute.

        Returns:
            FeaturePayload whose object-dtype ``data`` is shaped
            ``(channel_count, len(feature_set))``: each cell holds the value
            computed for that feature and channel (an ``np.ndarray`` for
            array-valued features, a ``float`` for ``tempo``, or a ``str`` for
            ``key``). ``frame.feature_names`` is ``feature_set``.

        Raises:
            ValueError: If feature_set is empty or contains unknown feature names.
        """
        if not isinstance(feature_set, tuple) or not feature_set:
            raise ValueError("MusicInformationRetriever: feature_set must be a non-empty tuple")
        for feature in feature_set:
            if feature not in self._allowed_features:
                raise ValueError(
                    f"MusicInformationRetriever: unknown feature {feature!r}; "
                    f"allowed: {sorted(self._allowed_features)!r}"
                )
        sr = int(signal.metadata.sample_rate_hz)
        channels = np.atleast_2d(signal.data)
        results = await ChannelFanOut.gather(
            [
                partial(MusicInformationRetriever._compute_mir_features, channel, sr, feature_set)
                for channel in channels
            ]
        )
        data = np.empty((channels.shape[0], len(feature_set)), dtype=object)
        for row, feature_values in enumerate(results):
            for col, feature in enumerate(feature_set):
                data[row, col] = feature_values[feature]
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:mir",
                channel_count=channels.shape[0],
                feature_names=feature_set,
            ),
            data=data,
        )

    @staticmethod
    def _compute_mir_features(
        mono: np.ndarray, sr: int, feature_set: tuple[str, ...]
    ) -> dict[str, Any]:
        """Compute the requested MIR features for a single channel.

        Returns a dict keyed by feature name; array-valued features stay as
        ``np.ndarray`` (no ``.tolist()`` conversion).
        """
        librosa = OptionalDependency.require("librosa", extra="signal", package="pirn-signal")
        result: dict[str, Any] = {}

        if "chroma" in feature_set:
            result["chroma"] = librosa.feature.chroma_stft(y=mono, sr=sr)

        if "spectral_contrast" in feature_set:
            result["spectral_contrast"] = librosa.feature.spectral_contrast(y=mono, sr=sr)

        if "tonnetz" in feature_set:
            harmonic = librosa.effects.harmonic(mono)
            result["tonnetz"] = librosa.feature.tonnetz(y=harmonic, sr=sr)

        if "tempo" in feature_set:
            tempo, _ = librosa.beat.beat_track(y=mono, sr=sr)
            result["tempo"] = float(np.atleast_1d(tempo)[0])

        if "key" in feature_set:
            chroma = librosa.feature.chroma_cqt(y=mono, sr=sr)
            chroma_mean = chroma.mean(axis=1)
            pitch_classes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            result["key"] = pitch_classes[int(np.argmax(chroma_mean))]

        if "harmonic" in feature_set:
            result["harmonic"] = librosa.effects.harmonic(mono)

        if "percussive" in feature_set:
            result["percussive"] = librosa.effects.percussive(mono)

        if "structure" in feature_set:
            mfcc = librosa.feature.mfcc(y=mono, sr=sr, n_mfcc=13)
            result["structure"] = librosa.segment.recurrence_matrix(mfcc, mode="affinity")

        return result
