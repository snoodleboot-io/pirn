"""``PitchEstimator`` — fundamental-frequency tracking.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate f_min_hz, f_max_hz, and algorithm.
    3. If algorithm == 'yin': compute the YIN difference function over short frames,
       find minima below a threshold, and refine via parabolic interpolation.
    4. If algorithm == 'pyin': probabilistic YIN — also outputs confidence values.
    5. If algorithm == 'autocorrelation': compute normalised autocorrelation per frame
       and locate the first peak in [f_min_hz, f_max_hz].
    6. Repeat independently for each channel and return a FeaturePayload with the
       f0 trajectory per channel.

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
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


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
    ) -> FeaturePayload:
        """Estimate the fundamental frequency trajectory from the audio signal.

        Args:
            signal: Audio signal to estimate pitch from.
            f_min_hz: Minimum detectable frequency in Hz (positive float).
            f_max_hz: Maximum detectable frequency in Hz (must exceed f_min_hz).
            algorithm: Pitch detection algorithm: ``yin``, ``pyin``, or ``autocorrelation``.

        Returns:
            FeaturePayload with ``data`` shaped ``(channel_count, n_frames)``: the
            f0 (Hz) trajectory per channel.

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
        sr = int(signal.frame.sample_rate_hz)
        if algorithm == "yin":
            estimator = PitchEstimator._estimate_pitch_yin
        elif algorithm == "pyin":
            estimator = PitchEstimator._estimate_pitch_pyin
        else:
            estimator = PitchEstimator._estimate_pitch_autocorrelation
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(asyncio.to_thread(estimator, channel, sr, f_min_hz, f_max_hz) for channel in channels)
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:pitch-{algorithm}",
                channel_count=channels.shape[0],
                feature_names=("f0_hz",),
            ),
            data=np.stack(results, axis=0),
        )

    @staticmethod
    def _estimate_pitch_yin(mono: np.ndarray, sr: int, fmin: float, fmax: float) -> np.ndarray:
        try:
            import librosa
        except ImportError as exc:
            raise ImportError(
                "PitchEstimator requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        return librosa.yin(mono, fmin=fmin, fmax=fmax, sr=sr)

    @staticmethod
    def _estimate_pitch_pyin(mono: np.ndarray, sr: int, fmin: float, fmax: float) -> np.ndarray:
        try:
            import librosa
        except ImportError as exc:
            raise ImportError(
                "PitchEstimator requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        f0, _voiced_flag, _voiced_probs = librosa.pyin(mono, fmin=fmin, fmax=fmax, sr=sr)
        return np.nan_to_num(f0)

    @staticmethod
    def _estimate_pitch_autocorrelation(
        mono: np.ndarray, sr: int, fmin: float, fmax: float
    ) -> np.ndarray:
        try:
            import librosa
        except ImportError as exc:
            raise ImportError(
                "PitchEstimator requires 'librosa'. Install via pip install pirn-signal[signal]"
            ) from exc
        frame_size = 2048
        hop = 512
        frames = librosa.util.frame(mono, frame_length=frame_size, hop_length=hop)
        f0_frames: list[float] = []
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
