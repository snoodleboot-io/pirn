"""``OnsetDetector`` — note / event onset detection.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate hop_length and threshold.
    3. Compute the STFT with the given hop_length.
    4. Derive the onset strength function: O(k) = sum_f max(0, |X(k,f)| - |X(k-1,f)|).
    5. Pick-peak the onset strength function with a threshold multiplied by its mean.
    6. Convert peak frame indices to times in seconds.
    7. Return a mapping with onset times and metadata.

Math:
    Spectral flux onset strength:

    $$O(k) = \\sum_{f} \\max\\!\\left(0,\\; |X(k, f)| - |X(k-1, f)|\\right)$$

    An onset is detected at frame $k$ if $O(k) > \\text{threshold} \\cdot \\bar{O}$
    and $O(k)$ is a local maximum.

References:
    - Bello, J.P. et al. (2005). "A tutorial on onset detection in music signals."
      IEEE Trans. Speech Audio Process., 13(5), 1035-1047.
    - McFee, B. et al. (2015). "librosa: Audio and music signal analysis in Python."
      Proc. SciPy 2015.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import librosa
import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _detect_onsets(mono: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    return librosa.onset.onset_detect(y=mono, sr=sr, hop_length=hop_length, units="time")


class OnsetDetector(Knot):
    """Detect onset times in an audio signal using ``librosa.onset.onset_detect``."""

    def __init__(
        self,
        *,
        signal: Knot,
        hop_length: Knot | int,
        threshold: Knot | float = 0.5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            hop_length=hop_length,
            threshold=threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        hop_length: int,
        threshold: float = 0.5,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Detect onset times in the audio signal.

        Args:
            signal: Audio signal to analyse for onset events.
            hop_length: Hop size in samples (positive integer).
            threshold: Peak-picking threshold multiplier (must be positive).

        Returns:
            Mapping containing ``onset_times_sec`` (list of floats) and ``signal_id``.

        Raises:
            ValueError: If hop_length or threshold are invalid.
        """
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError("OnsetDetector: hop_length must be a positive integer")
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            raise ValueError("OnsetDetector: threshold must be positive")
        mono = signal.data[0] if signal.data.ndim > 1 else signal.data
        sr = int(signal.frame.sample_rate_hz)
        onsets = await asyncio.to_thread(_detect_onsets, mono, sr, hop_length)
        return {
            "onset_times_sec": onsets.tolist(),
            "signal_id": signal.frame.signal_id,
        }
