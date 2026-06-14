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
    4. Return a mapping with signal_id and the list of computed feature names.

    librosa algorithms; formulae are defined within those routines.

References:
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
    - Müller, M. (2015). "Fundamentals of Music Processing." Springer.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, ClassVar

import librosa
import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload


def _compute_mir_features(
    mono: np.ndarray, sr: int, feature_set: tuple[str, ...]
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    if "chroma" in feature_set:
        chroma = librosa.feature.chroma_stft(y=mono, sr=sr)
        result["chroma"] = chroma.tolist()

    if "spectral_contrast" in feature_set:
        contrast = librosa.feature.spectral_contrast(y=mono, sr=sr)
        result["spectral_contrast"] = contrast.tolist()

    if "tonnetz" in feature_set:
        harmonic = librosa.effects.harmonic(mono)
        tn = librosa.feature.tonnetz(y=harmonic, sr=sr)
        result["tonnetz"] = tn.tolist()

    if "tempo" in feature_set:
        tempo, _ = librosa.beat.beat_track(y=mono, sr=sr)
        result["tempo"] = float(np.atleast_1d(tempo)[0])

    if "key" in feature_set:
        chroma = librosa.feature.chroma_cqt(y=mono, sr=sr)
        chroma_mean = chroma.mean(axis=1)
        pitch_classes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        result["key"] = pitch_classes[int(np.argmax(chroma_mean))]

    if "harmonic" in feature_set:
        harmonic = librosa.effects.harmonic(mono)
        result["harmonic"] = harmonic.tolist()

    if "percussive" in feature_set:
        percussive = librosa.effects.percussive(mono)
        result["percussive"] = percussive.tolist()

    if "structure" in feature_set:
        mfcc = librosa.feature.mfcc(y=mono, sr=sr, n_mfcc=13)
        recurrence = librosa.segment.recurrence_matrix(mfcc, mode="affinity")
        result["structure"] = recurrence.tolist()

    return result


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
        feature_set: Knot | tuple = ("chroma", "tempo", "key"),
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
    ) -> Mapping[str, Any]:
        """Extract the configured MIR feature set from the audio signal.

        Args:
            signal: Audio signal to extract MIR features from.
            feature_set: Non-empty tuple of feature names to compute.

        Returns:
            Mapping containing ``signal_id`` and computed feature arrays/scalars
            keyed by feature name.

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
        mono = signal.data[0] if signal.data.ndim > 1 else signal.data
        sr = int(signal.frame.sample_rate_hz)
        features = await asyncio.to_thread(_compute_mir_features, mono, sr, feature_set)
        return {"signal_id": signal.frame.signal_id, **features}
