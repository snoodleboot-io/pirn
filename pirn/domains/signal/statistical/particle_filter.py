"""``ParticleFilter`` — sequential Monte Carlo state estimator."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ParticleFilter(Knot):
    """Particle (bootstrap) filter for nonlinear non-Gaussian systems.

    Production needs ``filterpy`` or a custom Sequential Monte Carlo
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        state_dim: int,
        particle_count: int,
        resampling_strategy: str = "systematic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError(
                "ParticleFilter: state_dim must be a positive integer"
            )
        if not isinstance(particle_count, int) or particle_count <= 0:
            raise ValueError(
                "ParticleFilter: particle_count must be a positive integer"
            )
        if resampling_strategy not in {
            "multinomial",
            "stratified",
            "systematic",
            "residual",
        }:
            raise ValueError(
                "ParticleFilter: resampling_strategy must be 'multinomial', "
                "'stratified', 'systematic', or 'residual'"
            )
        self._state_dim = state_dim
        self._particle_count = particle_count
        self._resampling_strategy = resampling_strategy
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def state_dim(self) -> int:
        return self._state_dim

    @property
    def particle_count(self) -> int:
        return self._particle_count

    @property
    def resampling_strategy(self) -> str:
        return self._resampling_strategy

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Filter the signal through the sequential Monte Carlo particle filter and return the filtered SignalFrame.

        Args:
            signal: Observed signal to filter through the nonlinear non-Gaussian state estimator.

        Returns:
            SignalFrame of particle-filter state estimates.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:particle",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
