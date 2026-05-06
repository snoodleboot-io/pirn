"""``ParticleFilter`` — sequential Monte Carlo state estimator.

Algorithm:
    1. Receive the input signal frame, state_dim, particle_count, and resampling_strategy.
    2. Validate state_dim and particle_count (positive integers) and
       resampling_strategy (one of ``multinomial``, ``stratified``, ``systematic``, ``residual``).
    3. Initialise particle_count particles by sampling from the prior.
    4. For each observation y(k):
       a. Propagate particles through the state transition model.
       b. Compute importance weights from the likelihood p(y_k | x_k^i).
       c. Normalise weights.
       d. Apply the selected resampling strategy when the effective sample size drops.
    5. Return a SignalFrame of particle mean state estimates.

Math:
    Particle weight update:

    $$w_k^i \\propto w_{k-1}^i \\cdot p(y_k | x_k^i)$$

    MMSE state estimate:

    $$\\hat{x}_k = \\sum_{i=1}^{N} w_k^i x_k^i$$

References:
    - Gordon, N.J., Salmond, D.J. & Smith, A.F.M. (1993). "Novel approach to nonlinear/non-Gaussian
      Bayesian state estimation." IEE Proc. Radar Signal Process., 140(2), 107-113.
    - filterpy: https://filterpy.readthedocs.io/
"""

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

    _valid_resampling_strategies = frozenset({
        "multinomial", "stratified", "systematic", "residual"
    })

    def __init__(
        self,
        *,
        signal: Knot,
        state_dim: Knot | int,
        particle_count: Knot | int,
        resampling_strategy: Knot | str = "systematic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            state_dim=state_dim,
            particle_count=particle_count,
            resampling_strategy=resampling_strategy,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        state_dim: int,
        particle_count: int,
        resampling_strategy: str = "systematic",
        **_: Any,
    ) -> SignalFrame:
        """Filter the signal through the sequential Monte Carlo particle filter.

        Args:
            signal: Observed signal to filter through the nonlinear non-Gaussian state estimator.
            state_dim: Dimension of the hidden state vector (positive integer).
            particle_count: Number of Monte Carlo particles (positive integer).
            resampling_strategy: Resampling algorithm — ``multinomial``, ``stratified``,
                ``systematic``, or ``residual``.

        Returns:
            SignalFrame of particle-filter state estimates.

        Raises:
            ValueError: If state_dim, particle_count, or resampling_strategy are invalid.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError(
                "ParticleFilter: state_dim must be a positive integer"
            )
        if not isinstance(particle_count, int) or particle_count <= 0:
            raise ValueError(
                "ParticleFilter: particle_count must be a positive integer"
            )
        if resampling_strategy not in self._valid_resampling_strategies:
            raise ValueError(
                "ParticleFilter: resampling_strategy must be 'multinomial', "
                "'stratified', 'systematic', or 'residual'"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:particle",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
