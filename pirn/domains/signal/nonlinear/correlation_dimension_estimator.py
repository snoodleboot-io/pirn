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

import asyncio
from collections.abc import Mapping
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _delay_embed(signal_array: np.ndarray, embedding_dim: int, tau: int = 1) -> np.ndarray:
    """Build Takens delay embedding matrix of shape (N - (embedding_dim-1)*tau, embedding_dim)."""
    signal_length = len(signal_array)
    length = signal_length - (embedding_dim - 1) * tau
    if length <= 0:
        return np.empty((0, embedding_dim))
    return np.array(
        [
            signal_array[start_idx : start_idx + embedding_dim * tau : tau]
            for start_idx in range(length)
        ]
    )


def _corr_dim(signal_array: np.ndarray, embedding_dim: int, r_max: float) -> float:
    """Correlation dimension via Grassberger-Procaccia algorithm."""
    embedded = _delay_embed(signal_array, embedding_dim)
    n_pts = len(embedded)
    if n_pts < 4:
        return 0.0
    # Compute pairwise distances (upper triangle only)
    dists = []
    for i in range(n_pts):
        for j in range(i + 1, n_pts):
            dists.append(float(np.linalg.norm(embedded[i] - embedded[j])))
    dists_arr = np.array(dists)
    n_pairs = len(dists_arr)
    if n_pairs == 0:
        return 0.0
    r_min = float(np.min(dists_arr[dists_arr > 0])) if np.any(dists_arr > 0) else 1e-6
    radii = np.logspace(np.log10(r_min), np.log10(r_max), 20)
    log_r = []
    log_c = []
    for radius in radii:
        correlation_integral = float(np.sum(dists_arr < radius)) / n_pairs
        if correlation_integral > 0:
            log_r.append(float(np.log(radius)))
            log_c.append(float(np.log(correlation_integral)))
    if len(log_r) < 2:
        return 0.0
    coeffs = np.polyfit(log_r, log_c, 1)
    return float(max(0.0, coeffs[0]))


class CorrelationDimensionEstimator(Knot):
    """Correlation-dimension estimator (Grassberger-Procaccia)."""

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
        signal: SignalPayload,
        embedding_dim: int,
        radius_min: float,
        radius_max: float,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate the Grassberger-Procaccia correlation dimension from the signal.

        Args:
            signal: Signal payload to estimate the correlation dimension from.
            embedding_dim: Embedding dimension for phase-space reconstruction (positive integer).
            radius_min: Minimum radius for correlation integral (positive float).
            radius_max: Maximum radius for correlation integral (must exceed radius_min).

        Returns:
            Mapping containing ``correlation_dimension``, ``embedding_dim``, and ``max_radius``.

        Raises:
            ValueError: If embedding_dim, radius_min, or radius_max are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError(
                "CorrelationDimensionEstimator: embedding_dim must be a positive integer"
            )
        if not isinstance(radius_min, (int, float)) or radius_min <= 0:
            raise ValueError("CorrelationDimensionEstimator: radius_min must be positive")
        if not isinstance(radius_max, (int, float)) or radius_max <= radius_min:
            raise ValueError("CorrelationDimensionEstimator: radius_max must exceed radius_min")
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        dim = await asyncio.to_thread(
            _corr_dim, signal_array.astype(float), embedding_dim, float(radius_max)
        )
        return {
            "correlation_dimension": dim,
            "embedding_dim": embedding_dim,
            "max_radius": float(radius_max),
        }
