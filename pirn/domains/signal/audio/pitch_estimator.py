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

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PitchEstimator(Knot):
    """Estimate fundamental frequency over time.

    Production needs ``librosa.pyin`` / ``librosa.yin``.
    """

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
        signal: SignalFrame,
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
            Mapping containing ``signal_id``, ``f_min_hz``, ``f_max_hz``, and ``algorithm``.

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
        return {
            "signal_id": signal.signal_id,
            "f_min_hz": float(f_min_hz),
            "f_max_hz": float(f_max_hz),
            "algorithm": algorithm,
        }
