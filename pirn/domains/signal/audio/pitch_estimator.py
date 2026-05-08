"""``PitchEstimator`` — fundamental-frequency tracking.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate f_min_hz, f_max_hz, and algorithm.
    3. If algorithm == 'yin': compute the YIN difference function over short frames,
       find minima below a threshold, and refine via parabolic interpolation.
    4. If algorithm == 'pyin': probabilistic YIN — also outputs confidence values.
    5. If algorithm == 'autocorrelation': compute normalised autocorrelation per frame
       and locate the first peak in [f_min_hz, f_max_hz].
    6. Return a mapping with pitch estimates, confidence, and metadata.

Math:
    YIN cumulative mean normalised difference function:

    $$d'(\\tau) = \\begin{cases} 1 & \\tau = 0 \\\\ \\frac{d(\\tau)}{\\frac{1}{\\tau}\\sum_{j=1}^{\\tau} d(j)} & \\tau > 0 \\end{cases}$$

    where $d(\\tau) = \\sum_j (x_j - x_{j+\\tau})^2$ is the difference function.

    Fundamental frequency: $f_0 = f_s / \\tau^*$ where $\\tau^*$ is the chosen lag.

References:
    - De Cheveigné, A. & Kawahara, H. (2002). "YIN, a fundamental frequency estimator
      for speech and music." JASA, 111(4), 1917-1930.
    - Mauch, M. & Dixon, S. (2014). "pYIN: A fundamental frequency estimator using
      probabilistic threshold distributions." ICASSP 2014.
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


def _estimate_pitch_yin(mono: np.ndarray, sr: int, fmin: float, fmax: float) -> np.ndarray:
    return librosa.yin(mono, fmin=fmin, fmax=fmax, sr=sr)


def _estimate_pitch_pyin(mono: np.ndarray, sr: int, fmin: float, fmax: float) -> np.ndarray:
    f0, _voiced_flag, _voiced_probs = librosa.pyin(mono, fmin=fmin, fmax=fmax, sr=sr)
    return np.nan_to_num(f0)


def _estimate_pitch_autocorrelation(
    mono: np.ndarray, sr: int, fmin: float, fmax: float
) -> np.ndarray:
    frame_size = 2048
    hop = 512
    frames = librosa.util.frame(mono, frame_length=frame_size, hop_length=hop)
    f0_frames = []
    for frame in frames.T:
        ac = np.correlate(frame, frame, mode="full")[frame_size - 1 :]
        ac = ac / (ac[0] + 1e-10)
        min_lag = max(1, int(sr / fmax))
        max_lag = min(len(ac) - 1, int(sr / fmin))
        if min_lag >= max_lag:
            f0_frames.append(0.0)
            continue
        peak = int(np.argmax(ac[min_lag:max_lag])) + min_lag
        f0_frames.append(float(sr) / peak if peak > 0 else 0.0)
    return np.array(f0_frames, dtype=np.float32)


class PitchEstimator(Knot):
    """Estimate fundamental frequency over time using ``librosa.yin`` or ``librosa.pyin``."""

    def __init__(
        self,
        *,
        signal: Knot,
        f_min_hz: Knot | float,
        f_max_hz: Knot | float,
        algorithm: Knot | str = "yin",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            f_min_hz=f_min_hz,
            f_max_hz=f_max_hz,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        f_min_hz: float,
        f_max_hz: float,
        algorithm: str = "yin",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate the fundamental frequency trajectory from the audio signal.

        Args:
            signal: Audio signal to estimate pitch from.
            f_min_hz: Minimum detectable frequency in Hz (positive float).
            f_max_hz: Maximum detectable frequency in Hz (must exceed f_min_hz).
            algorithm: Pitch detection algorithm: ``yin``, ``pyin``, or ``autocorrelation``.

        Returns:
            Mapping containing ``f0_hz`` (list of floats per frame) and ``signal_id``.

        Raises:
            ValueError: If f_min_hz, f_max_hz, or algorithm are invalid.
        """
        if not isinstance(f_min_hz, (int, float)) or f_min_hz <= 0:
            raise ValueError("PitchEstimator: f_min_hz must be positive")
        if not isinstance(f_max_hz, (int, float)) or f_max_hz <= f_min_hz:
            raise ValueError("PitchEstimator: f_max_hz must exceed f_min_hz")
        if algorithm not in {"yin", "pyin", "autocorrelation"}:
            raise ValueError(
                "PitchEstimator: algorithm must be 'yin', 'pyin', or 'autocorrelation'"
            )
        mono = signal.data[0] if signal.data.ndim > 1 else signal.data
        sr = int(signal.frame.sample_rate_hz)
        if algorithm == "yin":
            f0 = await asyncio.to_thread(_estimate_pitch_yin, mono, sr, f_min_hz, f_max_hz)
        elif algorithm == "pyin":
            f0 = await asyncio.to_thread(_estimate_pitch_pyin, mono, sr, f_min_hz, f_max_hz)
        else:
            f0 = await asyncio.to_thread(
                _estimate_pitch_autocorrelation, mono, sr, f_min_hz, f_max_hz
            )
        return {
            "f0_hz": f0.tolist(),
            "signal_id": signal.frame.signal_id,
        }
