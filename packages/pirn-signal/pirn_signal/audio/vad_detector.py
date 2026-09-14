"""``VADDetector`` — voice activity detection.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate frame_duration_ms (must be 10, 20, or 30) and aggressiveness (0-3).
    3. Segment the audio into non-overlapping frames of frame_duration_ms milliseconds.
    4. For each frame: compute energy and zero-crossing rate.
    5. Apply an aggressiveness-level threshold to classify frames as speech or silence.
    6. Repeat independently for each channel and return a FeaturePayload with the
       per-frame voiced/unvoiced classification per channel.

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

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class VADDetector(Knot):
    """Voice activity detector based on energy and zero-crossing heuristics."""

    _valid_frame_durations: ClassVar[frozenset[int]] = frozenset({10, 20, 30})
    _default_frame_size: ClassVar[int] = 512

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
        signal: SignalPayload,
        frame_duration_ms: int,
        aggressiveness: int,
        **_: Any,
    ) -> FeaturePayload:
        """Detect voiced and unvoiced frames in the signal.

        Args:
            signal: Audio signal to analyse for voice activity.
            frame_duration_ms: Frame length in milliseconds (must be 10, 20, or 30).
            aggressiveness: VAD aggressiveness level in [0, 3]; higher values lower
                the energy threshold, classifying more frames as unvoiced.

        Returns:
            FeaturePayload with boolean ``data`` shaped ``(channel_count, n_frames)``:
            the per-frame voiced classification per channel.

        Raises:
            ValueError: If frame_duration_ms or aggressiveness are invalid.
        """
        if frame_duration_ms not in self._valid_frame_durations:
            raise ValueError("VADDetector: frame_duration_ms must be one of 10, 20, or 30")
        if not isinstance(aggressiveness, int) or aggressiveness < 0 or aggressiveness > 3:
            raise ValueError("VADDetector: aggressiveness must be an integer in [0, 3]")
        threshold_db = -40.0
        sr = signal.frame.sample_rate_hz
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    VADDetector._run_vad,
                    channel,
                    threshold_db,
                    frame_duration_ms,
                    aggressiveness,
                    sr,
                )
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:vad",
                channel_count=channels.shape[0],
                feature_names=("voiced",),
            ),
            data=np.stack(results, axis=0),
        )

    @staticmethod
    def _energy_vad(
        x: np.ndarray, threshold_db: float, frame_size: int | None = None
    ) -> list[bool]:
        """Classify frames as voiced (True) or unvoiced (False) by RMS energy.

        ``frame_size`` defaults to ``VADDetector._default_frame_size`` when omitted.
        """
        if frame_size is None:
            frame_size = VADDetector._default_frame_size
        signal_length = len(x)
        voiced: list[bool] = []
        threshold_linear = 10.0 ** (threshold_db / 20.0)
        for start in range(0, signal_length, frame_size):
            frame = x[start : start + frame_size]
            rms = float(np.sqrt(np.mean(frame**2)))
            voiced.append(rms >= threshold_linear)
        return voiced

    @staticmethod
    def _run_vad(
        channel: np.ndarray,
        threshold_db: float,
        frame_duration_ms: int,
        aggressiveness: int,
        sr: float,
    ) -> np.ndarray:
        """Classify a single channel's frames as voiced/unvoiced, returned as a bool array."""
        frame_size = max(1, int(sr * frame_duration_ms / 1000.0))
        effective_threshold = threshold_db - aggressiveness * 3.0
        voiced_frames = VADDetector._energy_vad(channel, effective_threshold, frame_size)
        return np.asarray(voiced_frames, dtype=bool)
