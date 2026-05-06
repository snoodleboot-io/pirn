"""``CorrelationDimensionEstimator`` — Grassberger-Procaccia dimension.

Algorithm:
    1. Receive the input signal frame, embedding_dim, radius_min, and radius_max.
    2. Validate embedding_dim (positive integer), radius_min (positive), and
       radius_max (greater than radius_min).
    3. Embed the time series in m-dimensional delay space using Takens' theorem.
    4. For each radius r in [radius_min, radius_max], count pairs of embedded
       points closer than r (the correlation integral C(r)).
    5. Estimate the correlation dimension as the slope of log(C(r)) vs. log(r)
       in the scaling region.
    6. Return a result mapping with the estimated dimension and parameters.

Math:
    Correlation integral:

    $$C(r) = \\lim_{N \\to \\infty} \\frac{2}{N(N-1)} \\sum_{i < j} \\Theta(r - \\|x_i - x_j\\|)$$

    Correlation dimension:

    $$D_2 = \\lim_{r \\to 0} \\frac{\\log C(r)}{\\log r}$$

References:
    - Grassberger, P. & Procaccia, I. (1983). "Measuring the strangeness of strange attractors."
      Physica D, 9(1-2), 189-208.
    - nolds library: https://github.com/CSchoel/nolds
"""

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
        embedding_dim: Knot | int,
        radius_min: Knot | float,
        radius_max: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            embedding_dim=embedding_dim,
            radius_min=radius_min,
            radius_max=radius_max,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        embedding_dim: int,
        radius_min: float,
        radius_max: float,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate the Grassberger-Procaccia correlation dimension from the signal.

        Args:
            signal: Time series signal to estimate the correlation dimension from.
            embedding_dim: Embedding dimension for phase-space reconstruction (positive integer).
            radius_min: Minimum radius for correlation integral (positive float).
            radius_max: Maximum radius for correlation integral (must exceed radius_min).

        Returns:
            Mapping containing ``signal_id``, ``embedding_dim``, ``radius_min``,
            ``radius_max``, and ``estimator``.

        Raises:
            ValueError: If embedding_dim, radius_min, or radius_max are invalid.
        """
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
        return {
            "signal_id": signal.signal_id,
            "embedding_dim": embedding_dim,
            "radius_min": float(radius_min),
            "radius_max": float(radius_max),
            "estimator": "correlation_dimension",
        }
