"""``KalmanFilter`` — linear-Gaussian Kalman state estimator.

Algorithm:
    1. Receive the observed signal payload plus process_noise and measurement_noise.
    2. Validate that both noise values are positive.
    3. Predict step: x̂(n|n-1) = x̂(n-1|n-1), P(n|n-1) = P(n-1|n-1) + Q.
    4. Update step: K = P(n|n-1) / (P(n|n-1) + R).
    5. Correct state: x̂(n|n) = x̂(n|n-1) + K (z(n) - x̂(n|n-1)).
    6. Update covariance: P(n|n) = (1 - K) P(n|n-1).
    7. Return a SignalPayload of Kalman-filtered state estimates.

Math:
    Scalar Kalman gain and state update:

    $$K(n) = \\frac{P(n|n-1)}{P(n|n-1) + R}$$

    $$\\hat{x}(n|n) = \\hat{x}(n|n-1) + K(n) \\left( z(n) - \\hat{x}(n|n-1) \\right)$$

    where:
    - $Q$ is the process noise variance
    - $R$ is the measurement noise variance

References:
    - Kalman, R.E. (1960). "A new approach to linear filtering and prediction problems."
      J. Basic Engineering, 82(1), 35-45.
    - Welch, G. & Bishop, G. (2006). "An Introduction to the Kalman Filter." UNC TR 95-041.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _kalman_1d(y: np.ndarray, q: float, r: float) -> np.ndarray:
    """Run a scalar 1-D Kalman filter and return the filtered signal."""
    n = len(y)
    x_est = np.zeros(n)
    x_hat = y[0]
    p = 1.0
    for i in range(n):
        p_pred = p + q
        k = p_pred / (p_pred + r)
        x_hat = x_hat + k * (y[i] - x_hat)
        p = (1.0 - k) * p_pred
        x_est[i] = x_hat
    return x_est


class KalmanFilter(Knot):
    """Standard scalar Kalman filter for 1-D signal smoothing."""

    def __init__(
        self,
        *,
        signal: Knot,
        process_noise: Knot | float,
        measurement_noise: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            process_noise=process_noise,
            measurement_noise=measurement_noise,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        process_noise: float,
        measurement_noise: float,
        **_: Any,
    ) -> SignalPayload:
        """Run the scalar Kalman filter over the input signal and return the filtered SignalPayload.

        Args:
            signal: Observed signal payload to filter through the Kalman state estimator.
            process_noise: Process noise variance Q (must be positive).
            measurement_noise: Measurement noise variance R (must be positive).

        Returns:
            SignalPayload of Kalman-filtered state estimates.

        Raises:
            ValueError: If process_noise or measurement_noise are not positive.
        """
        if not isinstance(process_noise, (int, float)) or process_noise <= 0:
            raise ValueError("KalmanFilter: process_noise must be positive")
        if not isinstance(measurement_noise, (int, float)) or measurement_noise <= 0:
            raise ValueError("KalmanFilter: measurement_noise must be positive")

        y = signal.data[0] if signal.data.ndim > 1 else signal.data

        result = await asyncio.to_thread(
            _kalman_1d, y, float(process_noise), float(measurement_noise)
        )

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:kalman",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[0],
            ),
            data=result,
        )
