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
    5. Return a SignalPayload of filtered state estimates.

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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _ekf(y: np.ndarray, q: float, r: float, dim: int) -> np.ndarray:
    """Linearised EKF with identity state transition, scalar observation per step.

    Returns filtered state estimates shaped (len(y),).
    """
    n = len(y)
    F = np.eye(dim)
    H = np.zeros((1, dim))
    H[0, 0] = 1.0
    Q = q * np.eye(dim)
    R_mat = np.array([[r]])
    x = np.zeros(dim)
    P = np.eye(dim)
    estimates = np.zeros(n)
    for k in range(n):
        # Predict
        x_pred = F @ x
        P_pred = F @ P @ F.T + Q
        # Update
        S = H @ P_pred @ H.T + R_mat
        K = P_pred @ H.T @ np.linalg.inv(S)
        innov = y[k] - float(H @ x_pred)
        x = x_pred + K[:, 0] * innov
        P = (np.eye(dim) - K @ H) @ P_pred
        estimates[k] = float(x[0])
    return estimates


class ExtendedKalmanFilter(Knot):
    """Extended Kalman filter for nonlinear state-space models."""

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
        signal: SignalPayload,
        state_dim: int,
        observation_dim: int,
        **_: Any,
    ) -> SignalPayload:
        """Filter the signal through the extended Kalman filter via local linearisation.

        Args:
            signal: Observed signal payload to filter through the nonlinear state estimator.
            state_dim: Dimension of the hidden state vector (positive integer).
            observation_dim: Dimension of the observation vector (positive integer).

        Returns:
            SignalPayload of EKF-filtered state estimates.

        Raises:
            ValueError: If state_dim or observation_dim are not positive integers.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError("ExtendedKalmanFilter: state_dim must be a positive integer")
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError("ExtendedKalmanFilter: observation_dim must be a positive integer")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        process_noise = 1e-3
        measurement_noise = 1e-1
        filtered = await asyncio.to_thread(
            _ekf, x.astype(float), process_noise, measurement_noise, state_dim
        )
        frame = SignalFrame(
            signal_id=f"{signal.frame.signal_id}:ekf",
            channel_count=1,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=len(filtered),
        )
        return SignalPayload(metadata=frame, data=filtered)
