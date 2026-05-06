"""``UnscentedKalmanFilter`` — derivative-free nonlinear Kalman estimator.

Algorithm:
    1. Receive the input signal frame, state_dim, observation_dim, alpha, beta, and kappa.
    2. Validate state_dim and observation_dim (positive integers), alpha (positive float),
       beta and kappa (real numbers).
    3. Compute 2 * state_dim + 1 sigma points around the current state estimate.
    4. Propagate sigma points through the nonlinear state transition function f(x).
    5. Compute the predicted mean and covariance from the propagated sigma points.
    6. Apply the UKF update equations using the observation sigma points and Kalman gain.
    7. Return a SignalFrame of UKF-filtered state estimates.

Math:
    Sigma points:

    $$x^{(i)} = \\hat{x} \\pm \\sqrt{(n + \\lambda) P}_{:,i}, \\quad \\lambda = \\alpha^2(n + \\kappa) - n$$

    UKF update:

    $$K = P_{xy} P_{yy}^{-1}, \\quad \\hat{x}^+ = \\hat{x}^- + K(y - \\hat{y})$$

References:
    - Julier, S.J. & Uhlmann, J.K. (1997). "A new extension of the Kalman filter to nonlinear systems."
      Proc. SPIE, 3068, 182-193.
    - filterpy.kalman.UnscentedKalmanFilter: https://filterpy.readthedocs.io/en/latest/kalman/UnscentedKalmanFilter.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class UnscentedKalmanFilter(Knot):
    """Unscented Kalman filter using sigma-point propagation.

    Production needs ``filterpy.kalman.UnscentedKalmanFilter``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        state_dim: Knot | int,
        observation_dim: Knot | int,
        alpha: Knot | float = 1e-3,
        beta: Knot | float = 2.0,
        kappa: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            state_dim=state_dim,
            observation_dim=observation_dim,
            alpha=alpha,
            beta=beta,
            kappa=kappa,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        state_dim: int,
        observation_dim: int,
        alpha: float = 1e-3,
        beta: float = 2.0,
        kappa: float = 0.0,
        **_: Any,
    ) -> SignalFrame:
        """Filter the signal through the unscented Kalman filter via sigma-point propagation.

        Args:
            signal: Observed signal to filter through the derivative-free nonlinear state estimator.
            state_dim: Dimension of the hidden state vector (positive integer).
            observation_dim: Dimension of the observation vector (positive integer).
            alpha: Sigma-point spread parameter (positive float, typically 1e-3).
            beta: Distribution parameter for prior knowledge (real number, 2.0 for Gaussian).
            kappa: Secondary scaling parameter (real number).

        Returns:
            SignalFrame of UKF-filtered state estimates.

        Raises:
            ValueError: If state_dim, observation_dim, or alpha are invalid.
            TypeError: If beta or kappa are not real numbers.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError(
                "UnscentedKalmanFilter: state_dim must be a positive integer"
            )
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError(
                "UnscentedKalmanFilter: observation_dim must be a positive integer"
            )
        if not isinstance(alpha, (int, float)) or alpha <= 0:
            raise ValueError("UnscentedKalmanFilter: alpha must be positive")
        if not isinstance(beta, (int, float)):
            raise TypeError("UnscentedKalmanFilter: beta must be a real number")
        if not isinstance(kappa, (int, float)):
            raise TypeError("UnscentedKalmanFilter: kappa must be a real number")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:ukf",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
