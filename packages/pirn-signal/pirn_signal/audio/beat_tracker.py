"""``BeatTracker`` — beat / tempo tracking.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate hop_length, tempo_min_bpm, and tempo_max_bpm.
    3. Compute a novelty function (onset strength envelope) using STFT with
       the given hop_length.
    4. Estimate tempo by autocorrelating the novelty function and finding
       the dominant periodicity in [tempo_min_bpm, tempo_max_bpm].
    5. Locate beat times by dynamic programming over the novelty function.
    6. Repeat independently for each channel and return a FeaturePayload with
       the tempo and beat frame indices per channel (NaN-padded to the largest
       beat count found).

Math:
    Beat period in samples:

    $$T_{\\text{beat}} = \\frac{60 \\cdot f_s}{\\text{tempo\\_bpm} \\cdot h}$$

    where $f_s$ is the sample rate and $h$ is the hop_length.

    Tempo search range: $\\text{tempo} \\in [\\text{tempo\\_min\\_bpm},\\, \\text{tempo\\_max\\_bpm}]$.

References:
    - Ellis, D.P.W. (2007). "Beat tracking by dynamic programming."
      J. New Music Research, 36(1), 51-60.
    - McFee, B. & Ellis, D.P.W. (2014). "Better beat tracking through robust onset
      aggregation." ICASSP 2014.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class BeatTracker(Knot):
    """Estimate tempo and beat times using ``librosa.beat.beat_track``."""

    def __init__(
        self,
        *,
        signal: Knot,
        hop_length: Knot | int,
        tempo_min_bpm: Knot | float = 30.0,
        tempo_max_bpm: Knot | float = 240.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            hop_length=hop_length,
            tempo_min_bpm=tempo_min_bpm,
            tempo_max_bpm=tempo_max_bpm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        hop_length: int,
        tempo_min_bpm: float = 30.0,
        tempo_max_bpm: float = 240.0,
        **_: Any,
    ) -> FeaturePayload:
        """Estimate tempo and beat times from the input signal.

        Args:
            signal: Audio signal to analyse for beat and tempo information.
            hop_length: Hop size in samples (positive integer).
            tempo_min_bpm: Minimum tempo in BPM (positive float).
            tempo_max_bpm: Maximum tempo in BPM (must exceed tempo_min_bpm).

        Returns:
            FeaturePayload with ``data`` shaped ``(channel_count, 1 + max_beat_count)``:
            column 0 is ``tempo_bpm``, the remaining columns are beat frame indices
            per channel, NaN-padded to the largest beat count found across channels.

        Raises:
            ValueError: If hop_length, tempo_min_bpm, or tempo_max_bpm are invalid.
        """
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("BeatTracker: hop_length must be a positive integer")
        if not isinstance(tempo_min_bpm, (int, float)) or tempo_min_bpm <= 0:
            raise ValueError("BeatTracker: tempo_min_bpm must be positive")
        if not isinstance(tempo_max_bpm, (int, float)) or tempo_max_bpm <= tempo_min_bpm:
            raise ValueError("BeatTracker: tempo_max_bpm must exceed tempo_min_bpm")
        sr = int(signal.frame.sample_rate_hz)
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(BeatTracker._track_beats, channel, sr, hop_length)
                for channel in channels
            )
        )
        max_beats = max((len(beat_frames) for _, beat_frames in results), default=0)
        rows = [
            [tempo, *beat_frames, *([float("nan")] * (max_beats - len(beat_frames)))]
            for tempo, beat_frames in results
        ]
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:beats",
                channel_count=channels.shape[0],
                feature_names=("tempo_bpm", *(f"beat_frame_{i}" for i in range(max_beats))),
            ),
            data=np.asarray(rows).reshape(channels.shape[0], 1 + max_beats),
        )

    @staticmethod
    def _track_beats(mono: np.ndarray, sr: int, hop_length: int) -> tuple[float, np.ndarray]:
        try:
            import librosa  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "BeatTracker requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        tempo, beat_frames = librosa.beat.beat_track(y=mono, sr=sr, hop_length=hop_length)
        return float(np.atleast_1d(tempo)[0]), beat_frames
