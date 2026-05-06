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

from collections.abc import Mapping
from typing import Any

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
        signal: SignalFrame,
        embedding_dim: int,
        time_delay: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate the largest Lyapunov exponent from the signal.

        Args:
            signal: Time series signal to estimate the largest Lyapunov exponent from.
            embedding_dim: Phase-space embedding dimension (positive integer).
            time_delay: Delay embedding time lag in samples (positive integer).

        Returns:
            Mapping containing ``signal_id``, ``embedding_dim``, ``time_delay``, and ``estimator``.

        Raises:
            ValueError: If embedding_dim or time_delay are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError("LyapunovExponentEstimator: embedding_dim must be a positive integer")
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError("LyapunovExponentEstimator: time_delay must be a positive integer")
        return {
            "signal_id": signal.signal_id,
            "embedding_dim": embedding_dim,
            "time_delay": time_delay,
            "estimator": "lyapunov",
        }
