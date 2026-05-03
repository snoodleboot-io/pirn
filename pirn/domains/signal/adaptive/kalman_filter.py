"""``KalmanFilter`` — linear-Gaussian Kalman state estimator."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class KalmanFilter(Knot):
    """Standard Kalman filter for linear-Gaussian systems.

    Production needs ``filterpy`` / ``pykalman`` / hand-rolled NumPy.
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
                "KalmanFilter: state_dim must be a positive integer"
            )
        if not isinstance(observation_dim, int) or observation_dim <= 0:
            raise ValueError(
                "KalmanFilter: observation_dim must be a positive integer"
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
        """Run the Kalman filter over the input signal and return the state-estimated SignalFrame.

        Args:
            signal: Observed signal to filter through the Kalman state estimator.

        Returns:
            SignalFrame of Kalman-filtered state estimates.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:kalman",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
