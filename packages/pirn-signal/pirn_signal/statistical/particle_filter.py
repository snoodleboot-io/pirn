"""``ParticleFilter`` — sequential Monte Carlo state estimator.

Algorithm:
    1. Receive the input signal frame, state_dim, particle_count, and resampling_strategy.
    2. Validate state_dim and particle_count (positive integers) and
       resampling_strategy (one of ``multinomial``, ``stratified``, ``systematic``, ``residual``).
    3. Initialise particle_count particles of dimension state_dim by sampling from
       the standard-normal prior.
    4. For each observation y(k):
       a. Propagate every particle's state through the random-walk transition model.
       b. Weight by the Gaussian likelihood of y(k) given the particle's observed
          component (component 0, as the Kalman knots in this sub-area do).
       c. Normalise weights.
       d. Resample with the requested strategy when the effective sample size drops
          below half the particle count.
    5. Repeat independently for each channel and return a SignalPayload of
       particle mean state estimates.

The Monte Carlo draws come from a seeded generator, so a re-run of the same
graph on the same input reproduces the same estimates — a filter whose output
changed between two replays of one run could not be audited.

Math:
    Particle weight update:

    $$w_k^i \\propto w_{k-1}^i \\cdot p(y_k | x_k^i)$$

    MMSE state estimate:

    $$\\hat{x}_k = \\sum_{i=1}^{N} w_k^i x_k^i$$

References:
    - Gordon, N.J., Salmond, D.J. & Smith, A.F.M. (1993). "Novel approach to nonlinear/non-Gaussian
      Bayesian state estimation." IEE Proc. Radar Signal Process., 140(2), 107-113.
    - Douc, R. & Cappe, O. (2005). "Comparison of resampling schemes for particle
      filtering." ISPA 2005, 64-69.
    - filterpy: https://filterpy.readthedocs.io/
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload


class ParticleFilter(Knot):
    """Particle (bootstrap) filter for nonlinear non-Gaussian systems."""

    _valid_resampling_strategies: ClassVar[frozenset[str]] = frozenset(
        {"multinomial", "stratified", "systematic", "residual"}
    )
    #: Seed for the Monte Carlo draws, so estimates are reproducible across runs.
    _seed: ClassVar[int] = 0

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
        signal: SignalPayload,
        state_dim: int,
        particle_count: int,
        resampling_strategy: str = "systematic",
        **_: Any,
    ) -> SignalPayload:
        """Filter the signal through the sequential Monte Carlo particle filter.

        Args:
            signal: Observed signal payload to filter through the nonlinear non-Gaussian state estimator.
            state_dim: Dimension of the hidden state vector (positive integer).
            particle_count: Number of Monte Carlo particles (positive integer).
            resampling_strategy: Resampling algorithm — ``multinomial``, ``stratified``,
                ``systematic``, or ``residual``.

        Returns:
            SignalPayload of particle-filter state estimates.

        Raises:
            ValueError: If state_dim, particle_count, or resampling_strategy are invalid.
        """
        if not isinstance(state_dim, int) or state_dim <= 0:
            raise ValueError("ParticleFilter: state_dim must be a positive integer")
        if not isinstance(particle_count, int) or particle_count <= 0:
            raise ValueError("ParticleFilter: particle_count must be a positive integer")
        if resampling_strategy not in self._valid_resampling_strategies:
            raise ValueError(
                "ParticleFilter: resampling_strategy must be 'multinomial', "
                "'stratified', 'systematic', or 'residual'"
            )
        process_noise = 1e-2
        measurement_noise = 1e-1
        channels = np.atleast_2d(signal.data).astype(float)
        filtered = await asyncio.gather(
            *(
                asyncio.to_thread(
                    ParticleFilter._particle_filter,
                    channel,
                    state_dim,
                    particle_count,
                    process_noise,
                    measurement_noise,
                    resampling_strategy,
                )
                for channel in channels
            )
        )
        return signal.derive("particle", np.stack(filtered, axis=0))

    @staticmethod
    def _resample(
        weights: np.ndarray,
        particle_count: int,
        strategy: str,
        generator: np.random.Generator,
    ) -> np.ndarray:
        """Draw ``particle_count`` particle indices with the requested scheme.

        The four schemes differ in how the unit interval is sampled against the
        weights' cumulative distribution (Douc & Cappe 2005):

        * ``multinomial`` — ``particle_count`` independent uniform draws.
        * ``stratified`` — one uniform draw inside each of N equal strata.
        * ``systematic`` — a single uniform offset, then a regular comb of spacing
          ``1/N`` (the lowest-variance scheme, and this knot's default).
        * ``residual`` — the integer part of ``N * w_i`` copies deterministically,
          the remainder drawn from the fractional weights.

        Args:
            weights: Normalised particle weights.
            particle_count: Number of particles to draw.
            strategy: One of the four scheme names.
            generator: Seeded RNG the draws come from.

        Returns:
            Array of ``particle_count`` indices into the particle set.
        """
        cumulative = np.cumsum(weights)
        cumulative[-1] = 1.0
        if strategy == "multinomial":
            positions = generator.random(particle_count)
        elif strategy == "stratified":
            positions = (
                np.arange(particle_count) + generator.random(particle_count)
            ) / particle_count
        elif strategy == "systematic":
            positions = (np.arange(particle_count) + generator.random()) / particle_count
        else:
            return ParticleFilter._residual_resample(weights, particle_count, generator)
        return np.searchsorted(cumulative, np.sort(positions)).astype(int)

    @staticmethod
    def _residual_resample(
        weights: np.ndarray, particle_count: int, generator: np.random.Generator
    ) -> np.ndarray:
        """Residual resampling: deterministic copies plus a drawn remainder."""
        copies = np.floor(particle_count * weights).astype(int)
        indices = np.repeat(np.arange(len(weights)), copies)
        remaining = particle_count - int(indices.size)
        if remaining > 0:
            residual = particle_count * weights - copies
            total = float(residual.sum())
            probabilities = (
                residual / total if total > 0 else np.full(len(weights), 1.0 / len(weights))
            )
            extra = np.searchsorted(np.cumsum(probabilities), generator.random(remaining))
            indices = np.concatenate([indices, np.clip(extra, 0, len(weights) - 1)])
        return indices.astype(int)

    @staticmethod
    def _particle_filter(
        observations: np.ndarray,
        state_dim: int,
        num_particles: int,
        process_noise_var: float,
        measurement_noise_var: float,
        strategy: str,
    ) -> np.ndarray:
        """Bootstrap particle filter over a ``state_dim``-dimensional random-walk state.

        Component 0 of the state is the observed one (the convention
        :class:`~pirn_signal.statistical.extended_kalman_filter.ExtendedKalmanFilter`
        uses); the remaining components are latent and carry their own process noise.

        Args:
            observations: One channel's samples.
            state_dim: Dimension of each particle's state vector.
            num_particles: Number of particles.
            process_noise_var: Random-walk variance per component per step.
            measurement_noise_var: Observation noise variance.
            strategy: Resampling scheme name.

        Returns:
            Weighted-mean estimates of the observed component, shaped
            ``(len(observations),)``.
        """
        generator = np.random.default_rng(ParticleFilter._seed)
        obs_count = len(observations)
        particles = generator.standard_normal((num_particles, state_dim))
        weights: np.ndarray = np.ones(num_particles) / num_particles
        estimates = np.zeros(obs_count)
        for obs_index in range(obs_count):
            # Propagate every state component through the random walk.
            particles = particles + np.sqrt(process_noise_var) * generator.standard_normal(
                (num_particles, state_dim)
            )
            observed = particles[:, 0]
            # Weight: Gaussian likelihood of the observation given the observed component.
            log_w = -0.5 * (observations[obs_index] - observed) ** 2 / measurement_noise_var
            log_w -= np.max(log_w)
            weights = np.exp(log_w)
            weights /= weights.sum()
            # MMSE estimate
            estimates[obs_index] = float(weights @ observed)
            # Effective sample size — resample if needed
            effective_sample_size = 1.0 / float(np.sum(weights**2))
            if effective_sample_size < num_particles / 2:
                indices = ParticleFilter._resample(weights, num_particles, strategy, generator)
                particles = particles[indices]
                weights = np.ones(num_particles) / num_particles
        return estimates
