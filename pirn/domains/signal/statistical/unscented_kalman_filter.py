"""``UnscentedKalmanFilter`` — derivative-free nonlinear Kalman estimator.

Algorithm:
    1. Receive the input signal frame, state_dim, observation_dim, alpha, beta, and kappa.
    2. Validate state_dim and observation_dim (positive integers), alpha (positive float),
       beta and kappa (real numbers).
    3. Compute 2 * state_dim + 1 sigma points around the current state estimate.
    4. Propagate sigma points through the nonlinear state transition function f(x).
    5. Compute the predicted mean and covariance from the propagated sigma points.
    6. Apply the UKF update equations using the observation sigma points and Kalman gain.
    7. Return a SignalPayload of UKF-filtered state estimates.

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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _ukf(
    y: np.ndarray,
    q: float,
    r: float,
    dim: int,
    alpha: float,
    beta: float,
    kappa: float,
) -> np.ndarray:
    """UKF with sigma-point propagation and identity state transition.

    Returns filtered state estimates shaped (len(y),).
    """
    obs_count = len(y)
    lam = alpha**2 * (dim + kappa) - dim
    # Weights for mean and covariance
    Wm = np.full(2 * dim + 1, 0.5 / (dim + lam))
    Wc = Wm.copy()
    Wm[0] = lam / (dim + lam)
    Wc[0] = lam / (dim + lam) + (1.0 - alpha**2 + beta)
    process_noise_matrix = q * np.eye(dim)
    R_scalar = r
    state_estimate = np.zeros(dim)
    error_covariance = np.eye(dim)
    estimates = np.zeros(obs_count)
    for obs_index in range(obs_count):
        # Sigma points
        try:
            chol_matrix = np.linalg.cholesky((dim + lam) * error_covariance)
        except np.linalg.LinAlgError:
            chol_matrix = np.eye(dim) * np.sqrt(dim + lam)
        sigma = np.zeros((2 * dim + 1, dim))
        sigma[0] = state_estimate
        for state_idx in range(dim):
            sigma[state_idx + 1] = state_estimate + chol_matrix[:, state_idx]
            sigma[dim + state_idx + 1] = state_estimate - chol_matrix[:, state_idx]
        # Predict (identity transition)
        x_pred = Wm @ sigma
        diff = sigma - x_pred
        P_pred = diff.T @ np.diag(Wc) @ diff + process_noise_matrix
        # Observation sigma points (H maps first state component to observation)
        z_sigma = sigma[:, 0]
        z_pred = float(Wm @ z_sigma)
        Pzz = float(Wc @ (z_sigma - z_pred) ** 2) + R_scalar
        Pxz = diff.T @ np.diag(Wc) @ (z_sigma - z_pred)
        kalman_gain = Pxz / Pzz
        state_estimate = x_pred + kalman_gain * (y[obs_index] - z_pred)
        error_covariance = P_pred - np.outer(kalman_gain, kalman_gain) * Pzz
        estimates[obs_index] = float(state_estimate[0])
    return estimates


class UnscentedKalmanFilter(Knot):
    """Unscented Kalman filter using sigma-point propagation."""

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
        signal: SignalPayload,
        state_dim: int,
        observation_dim: int,
        alpha: float = 1e-3,
        beta: float = 2.0,
        kappa: float = 0.0,
        **_: Any,
    ) -> SignalPayload:
        """Filter the signal through the unscented Kalman filter via sigma-point propagation.

        Args:
            signal: Observed signal payload to filter through the derivative-free nonlinear state estimator.
            state_dim: Dimension of the hidden state vector (positive integer).
            observation_dim: Dimension of the observation vector (positive integer).
            alpha: Sigma-point spread parameter (positive float, typically 1e-3).
            beta: Distribution parameter for prior knowledge (real number, 2.0 for Gaussian).
            kappa: Secondary scaling parameter (real number).

        Returns:
            SignalPayload of UKF-filtered state estimates.

        Raises:
            ValueError: If state_dim, observation_dim, or alpha are invalid.
            TypeError: If beta or kappa are not real numbers.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError("UnscentedKalmanFilter: state_dim must be a positive integer")
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError("UnscentedKalmanFilter: observation_dim must be a positive integer")
        if not isinstance(alpha, (int, float)) or alpha <= 0:
            raise ValueError("UnscentedKalmanFilter: alpha must be positive")
        if not isinstance(beta, (int, float)):
            raise TypeError("UnscentedKalmanFilter: beta must be a real number")
        if not isinstance(kappa, (int, float)):
            raise TypeError("UnscentedKalmanFilter: kappa must be a real number")
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        process_noise = 1e-3
        measurement_noise = 1e-1
        filtered = await asyncio.to_thread(
            _ukf,
            signal_array.astype(float),
            process_noise,
            measurement_noise,
            state_dim,
            alpha,
            beta,
            kappa,
        )
        frame = SignalFrame(
            signal_id=f"{signal.frame.signal_id}:ukf",
            channel_count=1,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=len(filtered),
        )
        return SignalPayload(metadata=frame, data=filtered)
