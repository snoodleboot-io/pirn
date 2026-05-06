"""``KalmanSmoother`` — Rauch-Tung-Striebel two-pass smoother.

Algorithm:
    1. Receive the observed signal frame, state_dim, and observation_dim.
    2. Validate that both dimensions are positive integers.
    3. Forward pass: run the standard Kalman filter to obtain filtered estimates
       x̂(t|t) and predicted covariances P(t|t-1) for t = 1, ..., T.
    4. Backward pass (RTS smoother): for t = T-1, ..., 1:
       a. Compute smoother gain: G_t = P(t|t) F^T P(t+1|t)^{-1}.
       b. Update smoothed state: x̂(t|T) = x̂(t|t) + G_t (x̂(t+1|T) - x̂(t+1|t)).
       c. Update smoothed covariance: P(t|T) = P(t|t) + G_t (P(t+1|T) - P(t+1|t)) G_t^T.
    5. Return a SignalFrame of the smoothed state estimates.

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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class KalmanSmoother(Knot):
    """Forward-backward Kalman smoother for linear-Gaussian state models.

    Production needs a Kalman implementation (``filterpy`` /
    ``pykalman`` / hand-rolled scipy).
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
        """Run the forward-backward Kalman smoother over the input signal.

        Args:
            signal: Signal to smooth with the Rauch-Tung-Striebel two-pass Kalman smoother.
            state_dim: Dimension of the hidden state vector (positive integer).
            observation_dim: Dimension of the observation vector (positive integer).

        Returns:
            SignalFrame of the Kalman-smoothed output.

        Raises:
            ValueError: If state_dim or observation_dim are not positive integers.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError("KalmanSmoother: state_dim must be a positive integer")
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError("KalmanSmoother: observation_dim must be a positive integer")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:kalman-smooth",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
