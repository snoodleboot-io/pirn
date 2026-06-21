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

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


def _kalman_1d(
    signal_array: np.ndarray, process_noise_var: float, measurement_noise_var: float
) -> np.ndarray:
    """Run a scalar 1-D Kalman filter and return the filtered signal."""
    sample_count = len(signal_array)
    x_est = np.zeros(sample_count)
    x_hat = signal_array[0]
    error_covariance = 1.0
    for sample_index in range(sample_count):
        p_pred = error_covariance + process_noise_var
        kalman_gain = p_pred / (p_pred + measurement_noise_var)
        x_hat = x_hat + kalman_gain * (signal_array[sample_index] - x_hat)
        error_covariance = (1.0 - kalman_gain) * p_pred
        x_est[sample_index] = x_hat
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

        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data

        result = await asyncio.to_thread(
            _kalman_1d, signal_array, float(process_noise), float(measurement_noise)
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
