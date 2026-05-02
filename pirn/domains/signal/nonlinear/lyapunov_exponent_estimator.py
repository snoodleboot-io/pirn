"""``LyapunovExponentEstimator`` — largest-Lyapunov-exponent estimation."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class LyapunovExponentEstimator(Knot):
    """Estimate the largest Lyapunov exponent of a time series.

    Production needs ``nolds`` or a hand-rolled Rosenstein implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        embedding_dim: int,
        time_delay: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError(
                "LyapunovExponentEstimator: embedding_dim must be a positive integer"
            )
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError(
                "LyapunovExponentEstimator: time_delay must be a positive integer"
            )
        self._embedding_dim = embedding_dim
        self._time_delay = time_delay
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    @property
    def time_delay(self) -> int:
        return self._time_delay

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        return {
            "signal_id": signal.signal_id,
            "embedding_dim": self._embedding_dim,
            "time_delay": self._time_delay,
            "estimator": "lyapunov",
        }
