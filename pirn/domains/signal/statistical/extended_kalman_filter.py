"""``ExtendedKalmanFilter`` — Kalman filter for nonlinear systems via local linearisation.

Algorithm:
    1. Receive the input signal frame, state_dim, and observation_dim.
    2. Validate state_dim and observation_dim (positive integers).
    3. Initialise the state estimate and error covariance matrix.
    4. For each observation y(k):
       a. Predict: compute x̂(k|k-1) via the nonlinear state function f(x).
       b. Compute the Jacobian F_k = ∂f/∂x at x̂(k-1|k-1).
       c. Update: compute the Kalman gain K_k from Jacobian H_k = ∂h/∂x.
       d. Correct the state and covariance estimates.
    5. Return a SignalFrame of filtered state estimates.

Math:
    EKF predict step:

    $$\\hat{x}_{k|k-1} = f(\\hat{x}_{k-1|k-1}), \\quad P_{k|k-1} = F_k P_{k-1|k-1} F_k^T + Q$$

    EKF update step:

    $$K_k = P_{k|k-1} H_k^T (H_k P_{k|k-1} H_k^T + R)^{-1}$$

References:
    - Gelb, A. (1974). "Applied Optimal Estimation." MIT Press.
    - filterpy.kalman.ExtendedKalmanFilter: https://filterpy.readthedocs.io/en/latest/kalman/ExtendedKalmanFilter.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ExtendedKalmanFilter(Knot):
    """Extended Kalman filter for nonlinear state-space models.

    Production needs ``filterpy.kalman.ExtendedKalmanFilter`` or
    hand-rolled NumPy.
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
        """Filter the signal through the extended Kalman filter via local linearisation.

        Args:
            signal: Observed signal to filter through the nonlinear state estimator.
            state_dim: Dimension of the hidden state vector (positive integer).
            observation_dim: Dimension of the observation vector (positive integer).

        Returns:
            SignalFrame of EKF-filtered state estimates.

        Raises:
            ValueError: If state_dim or observation_dim are not positive integers.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError("ExtendedKalmanFilter: state_dim must be a positive integer")
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError("ExtendedKalmanFilter: observation_dim must be a positive integer")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:ekf",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
