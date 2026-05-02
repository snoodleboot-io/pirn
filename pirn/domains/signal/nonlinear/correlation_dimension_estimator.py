"""``CorrelationDimensionEstimator`` — Grassberger-Procaccia dimension."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class CorrelationDimensionEstimator(Knot):
    """Correlation-dimension estimator (Grassberger-Procaccia).

    Production needs ``nolds`` or a hand-rolled implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        embedding_dim: int,
        radius_min: float,
        radius_max: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError(
                "CorrelationDimensionEstimator: embedding_dim must be a positive integer"
            )
        if not isinstance(radius_min, (int, float)) or radius_min <= 0:
            raise ValueError(
                "CorrelationDimensionEstimator: radius_min must be positive"
            )
        if not isinstance(radius_max, (int, float)) or radius_max <= radius_min:
            raise ValueError(
                "CorrelationDimensionEstimator: radius_max must exceed radius_min"
            )
        self._embedding_dim = embedding_dim
        self._radius_min = float(radius_min)
        self._radius_max = float(radius_max)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    @property
    def radius_min(self) -> float:
        return self._radius_min

    @property
    def radius_max(self) -> float:
        return self._radius_max

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        return {
            "signal_id": signal.signal_id,
            "embedding_dim": self._embedding_dim,
            "radius_min": self._radius_min,
            "radius_max": self._radius_max,
            "estimator": "correlation_dimension",
        }
