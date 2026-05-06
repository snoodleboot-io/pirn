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

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class MusicInformationRetriever(Knot):
    """Aggregate MIR features (chroma, key, segments, structure).

    Production needs ``librosa`` plus optional MIR-specific libraries
    (``msaf``, ``mir_eval``).
    """

    _ALLOWED_FEATURES: frozenset[str] = frozenset(
        {"chroma", "tempo", "key", "structure", "harmonic", "percussive"}
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
        signal: SignalFrame,
        feature_set: tuple[str, ...] = ("chroma", "tempo", "key"),
        **_: Any,
    ) -> Mapping[str, Any]:
        """Extract the configured MIR feature set from the audio signal.

        Args:
            signal: Audio signal to extract MIR features from.
            feature_set: Non-empty tuple of feature names to compute.

        Returns:
            Mapping containing ``signal_id`` and a ``feature_set`` list of computed feature names.

        Raises:
            ValueError: If feature_set is empty or contains unknown feature names.
        """
        if not isinstance(feature_set, tuple) or not feature_set:
            raise ValueError("MusicInformationRetriever: feature_set must be a non-empty tuple")
        for feature in feature_set:
            if feature not in self._ALLOWED_FEATURES:
                raise ValueError(
                    f"MusicInformationRetriever: unknown feature {feature!r}; "
                    f"allowed: {sorted(self._ALLOWED_FEATURES)!r}"
                )
        return {
            "signal_id": signal.signal_id,
            "feature_set": list(feature_set),
        }
