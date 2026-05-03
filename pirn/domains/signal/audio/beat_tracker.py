"""``BeatTracker`` — beat / tempo tracking."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BeatTracker(Knot):
    """Estimate tempo and beat times.

    Production needs ``librosa.beat.beat_track``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        hop_length: int,
        tempo_min_bpm: float = 30.0,
        tempo_max_bpm: float = 240.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError(
                "BeatTracker: hop_length must be a positive integer"
            )
        if not isinstance(tempo_min_bpm, (int, float)) or tempo_min_bpm <= 0:
            raise ValueError(
                "BeatTracker: tempo_min_bpm must be positive"
            )
        if not isinstance(tempo_max_bpm, (int, float)) or tempo_max_bpm <= tempo_min_bpm:
            raise ValueError(
                "BeatTracker: tempo_max_bpm must exceed tempo_min_bpm"
            )
        self._hop_length = hop_length
        self._tempo_min_bpm = float(tempo_min_bpm)
        self._tempo_max_bpm = float(tempo_max_bpm)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def hop_length(self) -> int:
        return self._hop_length

    @property
    def tempo_min_bpm(self) -> float:
        return self._tempo_min_bpm

    @property
    def tempo_max_bpm(self) -> float:
        return self._tempo_max_bpm

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        """Estimate tempo and beat times from the input signal and return a beat-tracking result mapping.

        Args:
            signal: Audio signal to analyse for beat and tempo information.

        Returns:
            Mapping containing ``signal_id``, ``hop_length``, ``tempo_min_bpm``, ``tempo_max_bpm``, and ``feature``.
        """
        return {
            "signal_id": signal.signal_id,
            "hop_length": self._hop_length,
            "tempo_min_bpm": self._tempo_min_bpm,
            "tempo_max_bpm": self._tempo_max_bpm,
            "feature": "beats",
        }
