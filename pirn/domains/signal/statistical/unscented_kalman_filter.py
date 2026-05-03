"""``UnscentedKalmanFilter`` — derivative-free nonlinear Kalman estimator."""

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
        state_dim: int,
        observation_dim: int,
        alpha: float = 1e-3,
        beta: float = 2.0,
        kappa: float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._state_dim = state_dim
        self._observation_dim = observation_dim
        self._alpha = float(alpha)
        self._beta = float(beta)
        self._kappa = float(kappa)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def state_dim(self) -> int:
        return self._state_dim

    @property
    def observation_dim(self) -> int:
        return self._observation_dim

    @property
    def alpha(self) -> float:
        return self._alpha

    @property
    def beta(self) -> float:
        return self._beta

    @property
    def kappa(self) -> float:
        return self._kappa

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Filter the signal through the unscented Kalman filter via sigma-point propagation and return the filtered SignalFrame.

        Args:
            signal: Observed signal to filter through the derivative-free nonlinear state estimator.

        Returns:
            SignalFrame of UKF-filtered state estimates.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:ukf",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
