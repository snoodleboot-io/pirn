"""``LyapunovExponentEstimator`` — largest-Lyapunov-exponent estimation.

Algorithm:
    1. Receive the input signal frame, embedding_dim, and time_delay.
    2. Validate embedding_dim and time_delay (both positive integers).
    3. Reconstruct the phase space via Takens delay embedding with the
       given embedding_dim and time_delay.
    4. For each trajectory point, locate the nearest neighbour and track
       the divergence of the trajectories over time.
    5. Estimate the largest Lyapunov exponent as the mean rate of divergence
       using the Rosenstein algorithm.
    6. Return a result mapping with the estimated exponent and parameters.

Math:
    Rosenstein divergence curve:

    $$d_j(i) = C_j \\cdot e^{\\lambda_1 (i \\Delta t)}$$

    Largest Lyapunov exponent:

    $$\\lambda_1 = \\frac{1}{\\Delta t} \\left\\langle \\ln d_j(i) \\right\\rangle_j$$

References:
    - Rosenstein, M.T., Collins, J.J. & De Luca, C.J. (1993). "A practical method for
      calculating largest Lyapunov exponents from small data sets." Physica D, 65(1-2), 117-134.
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


def _delay_embed(signal_array: np.ndarray, embedding_dim: int, tau: int) -> np.ndarray:
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


def _lyapunov(signal_array: np.ndarray, embedding_dim: int, tau: int) -> float:
    """Largest Lyapunov exponent via Rosenstein algorithm."""
    embedded = _delay_embed(signal_array, embedding_dim, tau)
    n_pts = len(embedded)
    if n_pts < 4:
        return 0.0
    divergences = []
    max_iter = min(50, n_pts // 4)
    for i in range(n_pts):
        dists = np.linalg.norm(embedded - embedded[i], axis=1)
        dists[i] = np.inf
        # Exclude temporally close neighbours
        for k in range(max(0, i - tau), min(n_pts, i + tau + 1)):
            dists[k] = np.inf
        nn = int(np.argmin(dists))
        divs = []
        for step in range(max_iter):
            if i + step >= n_pts or nn + step >= n_pts:
                break
            divergence_dist = float(np.linalg.norm(embedded[i + step] - embedded[nn + step]))
            if divergence_dist > 0:
                divs.append(np.log(divergence_dist))
        if divs:
            divergences.append(divs)
    if not divergences:
        return 0.0
    min_len = min(len(d) for d in divergences)
    mean_div = np.mean([d[:min_len] for d in divergences], axis=0)
    if len(mean_div) < 2:
        return 0.0
    coeffs = np.polyfit(np.arange(len(mean_div)), mean_div, 1)
    return float(coeffs[0])


class LyapunovExponentEstimator(Knot):
    """Estimate the largest Lyapunov exponent of a time series."""

    def __init__(
        self,
        *,
        signal: Knot,
        embedding_dim: Knot | int,
        time_delay: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            embedding_dim=embedding_dim,
            time_delay=time_delay,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        embedding_dim: int,
        time_delay: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate the largest Lyapunov exponent from the signal.

        Args:
            signal: Signal payload to estimate the largest Lyapunov exponent from.
            embedding_dim: Phase-space embedding dimension (positive integer).
            time_delay: Delay embedding time lag in samples (positive integer).

        Returns:
            Mapping containing ``lyapunov_exponent``, ``embedding_dim``, and ``time_delay``.

        Raises:
            ValueError: If embedding_dim or time_delay are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError("LyapunovExponentEstimator: embedding_dim must be a positive integer")
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError("LyapunovExponentEstimator: time_delay must be a positive integer")
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        lam = await asyncio.to_thread(
            _lyapunov, signal_array.astype(float), embedding_dim, time_delay
        )
        return {
            "lyapunov_exponent": lam,
            "embedding_dim": embedding_dim,
            "time_delay": time_delay,
        }
