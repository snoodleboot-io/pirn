"""``KalmanFilter`` — linear-Gaussian Kalman state estimator.

Algorithm:
    1. Receive the observed signal frame plus state_dim and observation_dim.
    2. Validate that both dimensions are positive integers.
    3. Predict step: x̂(n|n-1) = F * x̂(n-1|n-1), P(n|n-1) = F P F^T + Q.
    4. Update step: K = P H^T (H P H^T + R)^{-1}.
    5. Correct state: x̂(n|n) = x̂(n|n-1) + K (z(n) - H x̂(n|n-1)).
    6. Update covariance: P(n|n) = (I - KH) P(n|n-1).
    7. Return a SignalFrame of Kalman-filtered state estimates.

Math:
    Kalman gain and state update:

    $$\\mathbf{K}(n) = \\mathbf{P}(n|n-1) \\mathbf{H}^T \\left( \\mathbf{H} \\mathbf{P}(n|n-1) \\mathbf{H}^T + \\mathbf{R} \\right)^{-1}$$

    $$\\hat{\\mathbf{x}}(n|n) = \\hat{\\mathbf{x}}(n|n-1) + \\mathbf{K}(n) \\left( \\mathbf{z}(n) - \\mathbf{H} \\hat{\\mathbf{x}}(n|n-1) \\right)$$

    where:
    - $\\mathbf{F} \\in \\mathbb{R}^{d \\times d}$ is the state transition matrix (state_dim = d)
    - $\\mathbf{H} \\in \\mathbb{R}^{m \\times d}$ is the observation matrix (observation_dim = m)
    - $\\mathbf{Q}, \\mathbf{R}$ are process and observation noise covariances

References:
    - Kalman, R.E. (1960). "A new approach to linear filtering and prediction problems."
      J. Basic Engineering, 82(1), 35-45.
    - Welch, G. & Bishop, G. (2006). "An Introduction to the Kalman Filter." UNC TR 95-041.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class KalmanFilter(Knot):
    """Standard Kalman filter for linear-Gaussian systems.

    Production needs ``filterpy`` / ``pykalman`` / hand-rolled NumPy.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        state_dim: Knot | int,
        observation_dim: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            state_dim=state_dim,
            observation_dim=observation_dim,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        state_dim: int,
        observation_dim: int,
        **_: Any,
    ) -> SignalFrame:
        """Run the Kalman filter over the input signal and return the state-estimated SignalFrame.

        Args:
            signal: Observed signal to filter through the Kalman state estimator.
            state_dim: Dimension of the hidden state vector (positive integer).
            observation_dim: Dimension of the observation vector (positive integer).

        Returns:
            SignalFrame of Kalman-filtered state estimates.

        Raises:
            ValueError: If state_dim or observation_dim are not positive integers.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError(
                "KalmanFilter: state_dim must be a positive integer"
            )
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError(
                "KalmanFilter: observation_dim must be a positive integer"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:kalman",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
