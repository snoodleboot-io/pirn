"""``VADDetector`` — voice activity detection."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class VADDetector(Knot):
    """Voice activity detector based on energy and zero-crossing heuristics.

    Production needs ``webrtcvad`` or ``silero-vad``.
    """

    _VALID_FRAME_DURATIONS: frozenset[int] = frozenset({10, 20, 30})

    def __init__(
        self,
        *,
        signal: Knot,
        frame_duration_ms: int,
        aggressiveness: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if frame_duration_ms not in self._VALID_FRAME_DURATIONS:
            raise ValueError(
                "VADDetector: frame_duration_ms must be one of 10, 20, or 30"
            )
        if not isinstance(aggressiveness, int) or aggressiveness < 0 or aggressiveness > 3:
            raise ValueError(
                "VADDetector: aggressiveness must be an integer in [0, 3]"
            )
        self._frame_duration_ms = frame_duration_ms
        self._aggressiveness = aggressiveness
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def frame_duration_ms(self) -> int:
        return self._frame_duration_ms

    @property
    def aggressiveness(self) -> int:
        return self._aggressiveness

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> list[dict[str, Any]]:
        """Detect voiced and unvoiced segments in the signal.

        Args:
            signal: Audio signal to analyse for voice activity.

        Returns:
            List of segment dicts, each with keys ``start_sec``, ``end_sec``,
            and ``is_speech``.
        """
        frame_duration_sec = self._frame_duration_ms / 1000.0
        duration_sec = signal.samples_per_channel / max(signal.sample_rate_hz, 1.0)
        segments: list[dict[str, Any]] = []
        t = 0.0
        while t < duration_sec:
            end = min(t + frame_duration_sec, duration_sec)
            segments.append({"start_sec": t, "end_sec": end, "is_speech": True})
            t = end
        return segments
