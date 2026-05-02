"""``MusicInformationRetriever`` — high-level MIR feature aggregator."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class MusicInformationRetriever(Knot):
    """Aggregate MIR features (chroma, key, segments, structure).

    Production needs ``librosa`` plus optional MIR-specific libraries
    (``msaf``, ``mir_eval``).
    """

    def __init__(
        self,
        *,
        signal: Knot,
        feature_set: tuple[str, ...] = ("chroma", "tempo", "key"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(feature_set, tuple) or not feature_set:
            raise ValueError(
                "MusicInformationRetriever: feature_set must be a non-empty tuple"
            )
        allowed = {
            "chroma",
            "tempo",
            "key",
            "structure",
            "harmonic",
            "percussive",
        }
        for feature in feature_set:
            if feature not in allowed:
                raise ValueError(
                    f"MusicInformationRetriever: unknown feature {feature!r}; "
                    f"allowed: {sorted(allowed)!r}"
                )
        self._feature_set = feature_set
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def feature_set(self) -> tuple[str, ...]:
        return self._feature_set

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        return {
            "signal_id": signal.signal_id,
            "feature_set": list(self._feature_set),
        }
