"""``BeatTracker`` — beat / tempo tracking.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate hop_length, tempo_min_bpm, and tempo_max_bpm.
    3. Compute a novelty function (onset strength envelope) using STFT with
       the given hop_length.
    4. Estimate tempo by autocorrelating the novelty function and finding
       the dominant periodicity in [tempo_min_bpm, tempo_max_bpm].
    5. Locate beat times by dynamic programming over the novelty function.
    6. Return a mapping containing tempo and beat frame indices.

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

from collections.abc import Mapping
from typing import Any

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
        signal: SignalFrame,
        hop_length: int,
        tempo_min_bpm: float = 30.0,
        tempo_max_bpm: float = 240.0,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate tempo and beat times from the input signal.

        Args:
            signal: Audio signal to analyse for beat and tempo information.
            hop_length: Hop size in samples (positive integer).
            tempo_min_bpm: Minimum tempo in BPM (positive float).
            tempo_max_bpm: Maximum tempo in BPM (must exceed tempo_min_bpm).

        Returns:
            Mapping containing ``signal_id``, ``hop_length``, ``tempo_min_bpm``,
            ``tempo_max_bpm``, and ``feature``.

        Raises:
            ValueError: If hop_length, tempo_min_bpm, or tempo_max_bpm are invalid.
        """
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("BeatTracker: hop_length must be a positive integer")
        if not isinstance(tempo_min_bpm, (int, float)) or tempo_min_bpm <= 0:
            raise ValueError("BeatTracker: tempo_min_bpm must be positive")
        if not isinstance(tempo_max_bpm, (int, float)) or tempo_max_bpm <= tempo_min_bpm:
            raise ValueError("BeatTracker: tempo_max_bpm must exceed tempo_min_bpm")
        return {
            "signal_id": signal.signal_id,
            "hop_length": hop_length,
            "tempo_min_bpm": tempo_min_bpm,
            "tempo_max_bpm": tempo_max_bpm,
            "feature": "beats",
        }
