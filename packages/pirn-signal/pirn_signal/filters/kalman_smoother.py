"""``KalmanSmoother`` — Rauch-Tung-Striebel two-pass smoother.

Algorithm:
    1. Receive the observed signal payload and state_dim.
    2. Validate that state_dim is a positive integer no smaller than the signal's
       channel count — the observation vector at each step *is* the channel vector,
       so the observation dimension is the signal's own channel count and is read
       from the payload rather than declared as a second, contradictable input.
    3. Run the Rauch-Tung-Striebel smoother.
    4. Return a SignalPayload of the smoothed output.

Math:
    RTS smoother gain:

    $$\\mathbf{G}_t = \\mathbf{P}(t|t) \\mathbf{F}^T \\mathbf{P}^{-1}(t+1|t)$$

    Smoothed state update:

    $$\\hat{\\mathbf{x}}(t|T) = \\hat{\\mathbf{x}}(t|t) + \\mathbf{G}_t \\left( \\hat{\\mathbf{x}}(t+1|T) - \\hat{\\mathbf{x}}(t+1|t) \\right)$$

References:
    - Rauch, H.E., Tung, F. & Striebel, C.T. (1965). "Maximum likelihood estimates of
      linear dynamic systems." AIAA Journal, 3(8), 1445-1450.
    - Sarkka, S. (2013). "Bayesian Filtering and Smoothing." Cambridge University Press.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload


class KalmanSmoother(Knot):
    """Forward-backward Kalman smoother for linear-Gaussian state models."""

    def __init__(
        self,
        *,
        signal: Knot,
        state_dim: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            state_dim=state_dim,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        state_dim: int,
        **_: Any,
    ) -> SignalPayload:
        """Run the forward-backward Kalman smoother over the input signal.

        Args:
            signal: Signal payload to smooth with the Rauch-Tung-Striebel two-pass Kalman smoother.
            state_dim: Dimension of the hidden state vector (positive integer, at
                least the signal's channel count, since each channel is one observed
                component of the state).

        Returns:
            SignalPayload of the Kalman-smoothed output.

        Raises:
            ValueError: If state_dim is not a positive integer, or is smaller than the
                signal's channel count.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError("KalmanSmoother: state_dim must be a positive integer")
        observation_dim = np.atleast_2d(signal.data).shape[0]
        if state_dim < observation_dim:
            raise ValueError(
                f"KalmanSmoother: state_dim ({state_dim}) must be at least the signal's "
                f"channel count ({observation_dim}) — every channel is one observed "
                f"component of the state vector"
            )

        smoothed = await asyncio.to_thread(KalmanSmoother._rts_smoother, signal.data, state_dim)
        return signal.derive(
            "kalman-smooth",
            np.asarray(smoothed),
        )

    @staticmethod
    def _rts_smoother(data: np.ndarray, state_dim: int) -> np.ndarray:
        """Run a scalar RTS smoother over a 1-D or 2-D signal array.

        Uses a simple random-walk state model (F=I, H=I truncated to obs_dim,
        Q=I*0.01, R=I) as a self-contained numpy implementation.

        Args:
            data: Signal array, shape (samples,) or (channels, samples).
            state_dim: Hidden state dimension.

        Returns:
            Smoothed array with the same shape as data.
        """
        flat = data.ndim == 1
        if flat:
            arr = data[np.newaxis, :]
        else:
            arr = data

        channels, n_samples = arr.shape
        obs_dim = channels

        f_mat = np.eye(state_dim)
        h_mat = np.zeros((obs_dim, state_dim))
        h_mat[:, :obs_dim] = np.eye(obs_dim)
        q_mat = np.eye(state_dim) * 0.01
        r_mat = np.eye(obs_dim)

        x_filt = np.zeros((n_samples, state_dim))
        p_filt = np.zeros((n_samples, state_dim, state_dim))
        x_pred = np.zeros((n_samples, state_dim))
        p_pred = np.zeros((n_samples, state_dim, state_dim))

        state_estimate = np.zeros(state_dim)
        error_covariance = np.eye(state_dim)

        for t in range(n_samples):
            x_p = f_mat @ state_estimate
            p_p = f_mat @ error_covariance @ f_mat.T + q_mat
            x_pred[t] = x_p
            p_pred[t] = p_p

            innov = arr[:, t] - h_mat @ x_p
            s_mat = h_mat @ p_p @ h_mat.T + r_mat
            k_gain = p_p @ h_mat.T @ np.linalg.inv(s_mat)
            state_estimate = x_p + k_gain @ innov
            error_covariance = (np.eye(state_dim) - k_gain @ h_mat) @ p_p
            x_filt[t] = state_estimate
            p_filt[t] = error_covariance

        x_smooth = x_filt.copy()
        p_smooth = p_filt.copy()

        for t in range(n_samples - 2, -1, -1):
            g_gain = p_filt[t] @ f_mat.T @ np.linalg.inv(p_pred[t + 1])
            x_smooth[t] = x_filt[t] + g_gain @ (x_smooth[t + 1] - x_pred[t + 1])
            p_smooth[t] = p_filt[t] + g_gain @ (p_smooth[t + 1] - p_pred[t + 1]) @ g_gain.T

        smoothed_obs = h_mat @ x_smooth.T
        if flat:
            return smoothed_obs[0]
        return smoothed_obs
