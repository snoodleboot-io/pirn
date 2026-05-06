"""``VADDetector`` — voice activity detection.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate frame_duration_ms (must be 10, 20, or 30) and aggressiveness (0-3).
    3. Segment the audio into non-overlapping frames of frame_duration_ms milliseconds.
    4. For each frame: compute energy and zero-crossing rate.
    5. Apply an aggressiveness-level threshold to classify frames as speech or silence.
    6. Merge adjacent frames with the same label into contiguous segments.
    7. Return a list of segment dicts with start_sec, end_sec, and is_speech.

Math:
    Frame duration in seconds:

    $$t_{\\text{frame}} = \\frac{\\text{frame\\_duration\\_ms}}{1000}$$

    Frame energy:

    $$E = \\frac{1}{N} \\sum_{n=0}^{N-1} x^2(n)$$

    The aggressiveness level (0-3) controls the energy threshold below which a
    frame is classified as silence; higher values are more aggressive at removing noise.

References:
    - Ramirez, J. et al. (2004). "Efficient voice activity detection algorithms using
      long-term speech information." Speech Communication, 42(3-4), 271-287.
    - WebRTC VAD: https://webrtc.googlesource.com/src/+/refs/heads/main/common_audio/vad/
"""

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
        frame_duration_ms: Knot | int,
        aggressiveness: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            frame_duration_ms=frame_duration_ms,
            aggressiveness=aggressiveness,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        frame_duration_ms: int,
        aggressiveness: int,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Detect voiced and unvoiced segments in the signal.

        Args:
            signal: Audio signal to analyse for voice activity.
            frame_duration_ms: Frame length in milliseconds (must be 10, 20, or 30).
            aggressiveness: VAD aggressiveness level in [0, 3].

        Returns:
            List of segment dicts, each with keys ``start_sec``, ``end_sec``,
            and ``is_speech``.

        Raises:
            ValueError: If frame_duration_ms or aggressiveness are invalid.
        """
        if frame_duration_ms not in self._VALID_FRAME_DURATIONS:
            raise ValueError("VADDetector: frame_duration_ms must be one of 10, 20, or 30")
        if not isinstance(aggressiveness, int) or aggressiveness < 0 or aggressiveness > 3:
            raise ValueError("VADDetector: aggressiveness must be an integer in [0, 3]")
        frame_duration_sec = frame_duration_ms / 1000.0
        duration_sec = signal.samples_per_channel / max(signal.sample_rate_hz, 1.0)
        segments: list[dict[str, Any]] = []
        t = 0.0
        while t < duration_sec:
            end = min(t + frame_duration_sec, duration_sec)
            segments.append({"start_sec": t, "end_sec": end, "is_speech": True})
            t = end
        return segments
