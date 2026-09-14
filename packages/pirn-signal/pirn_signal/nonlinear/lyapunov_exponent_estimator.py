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
    6. Repeat independently for each channel and return a FeaturePayload with
       one Lyapunov exponent per channel.

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
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.nonlinear._delay_embedding import DelayEmbedding
from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


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
    ) -> FeaturePayload:
        """Estimate the largest Lyapunov exponent from the signal.

        Args:
            signal: Signal payload to estimate the largest Lyapunov exponent from.
            embedding_dim: Phase-space embedding dimension (positive integer).
            time_delay: Delay embedding time lag in samples (positive integer).

        Returns:
            FeaturePayload with one ``lyapunov_exponent`` value per channel.

        Raises:
            ValueError: If embedding_dim or time_delay are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError("LyapunovExponentEstimator: embedding_dim must be a positive integer")
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError("LyapunovExponentEstimator: time_delay must be a positive integer")
        channels = np.atleast_2d(signal.data).astype(float)
        values = await asyncio.gather(
            *(
                asyncio.to_thread(
                    LyapunovExponentEstimator._lyapunov, channel, embedding_dim, time_delay
                )
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:lyapunov-exponent",
                channel_count=channels.shape[0],
                feature_names=("lyapunov_exponent",),
            ),
            data=np.asarray(values).reshape(channels.shape[0], 1),
        )

    @staticmethod
    def _lyapunov(signal_array: NDArray[np.float64], embedding_dim: int, tau: int) -> float:
        """Largest Lyapunov exponent via Rosenstein algorithm."""
        embedded = DelayEmbedding.embed(signal_array, embedding_dim, tau)
        n_pts = len(embedded)
        if n_pts < 4:
            return 0.0
        divergences: list[list[float]] = []
        max_iter = min(50, n_pts // 4)
        for i in range(n_pts):
            reference_point: NDArray[np.float64] = embedded[i]
            dists: NDArray[np.float64] = np.linalg.norm(embedded - reference_point, axis=1)
            dists[i] = np.inf
            # Exclude temporally close neighbours
            for k in range(max(0, i - tau), min(n_pts, i + tau + 1)):
                dists[k] = np.inf
            nn = int(np.argmin(dists))
            divs: list[float] = []
            for step in range(max_iter):
                if i + step >= n_pts or nn + step >= n_pts:
                    break
                separation: NDArray[np.float64] = embedded[i + step] - embedded[nn + step]
                divergence_dist = float(np.linalg.norm(separation))
                if divergence_dist > 0:
                    divs.append(float(np.log(divergence_dist)))
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
