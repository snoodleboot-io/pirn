"""``PitchEstimator`` — fundamental-frequency tracking."""

from __future__ import annotations

from typing import Any, Mapping

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
        f_min_hz: float,
        f_max_hz: float,
        algorithm: str = "yin",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(f_min_hz, (int, float)) or f_min_hz <= 0:
            raise ValueError(
                "PitchEstimator: f_min_hz must be positive"
            )
        if not isinstance(f_max_hz, (int, float)) or f_max_hz <= f_min_hz:
            raise ValueError(
                "PitchEstimator: f_max_hz must exceed f_min_hz"
            )
        if algorithm not in {"yin", "pyin", "autocorrelation"}:
            raise ValueError(
                "PitchEstimator: algorithm must be 'yin', 'pyin', or 'autocorrelation'"
            )
        self._f_min_hz = float(f_min_hz)
        self._f_max_hz = float(f_max_hz)
        self._algorithm = algorithm
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def f_min_hz(self) -> float:
        return self._f_min_hz

    @property
    def f_max_hz(self) -> float:
        return self._f_max_hz

    @property
    def algorithm(self) -> str:
        return self._algorithm

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        """Estimate the fundamental frequency trajectory from the audio signal and return a pitch result mapping.

        Args:
            signal: Audio signal to estimate pitch from.

        Returns:
            Mapping containing ``signal_id``, ``f_min_hz``, ``f_max_hz``, and ``algorithm``.
        """
        return {
            "signal_id": signal.signal_id,
            "f_min_hz": self._f_min_hz,
            "f_max_hz": self._f_max_hz,
            "algorithm": self._algorithm,
        }
