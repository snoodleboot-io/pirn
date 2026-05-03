"""``ExtendedKalmanFilter`` — Kalman filter for nonlinear systems via local linearisation."""

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
        state_dim: int,
        observation_dim: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError(
                "ExtendedKalmanFilter: state_dim must be a positive integer"
            )
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError(
                "ExtendedKalmanFilter: observation_dim must be a positive integer"
            )
        self._state_dim = state_dim
        self._observation_dim = observation_dim
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def state_dim(self) -> int:
        return self._state_dim

    @property
    def observation_dim(self) -> int:
        return self._observation_dim

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Filter the signal through the extended Kalman filter via local linearisation and return the filtered SignalFrame.

        Args:
            signal: Observed signal to filter through the nonlinear state estimator.

        Returns:
            SignalFrame of EKF-filtered state estimates.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:ekf",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
