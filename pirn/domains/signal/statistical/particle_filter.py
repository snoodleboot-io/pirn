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
       d. Apply systematic resampling when the effective sample size drops.
    5. Return a SignalPayload of particle mean state estimates.

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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _systematic_resample(weights: np.ndarray, n: int) -> np.ndarray:
    """Systematic resampling; returns array of indices."""
    positions = (np.arange(n) + np.random.uniform()) / n
    cumsum = np.cumsum(weights)
    indices = np.zeros(n, dtype=int)
    i, j = 0, 0
    while i < n:
        if positions[i] < cumsum[j]:
            indices[i] = j
            i += 1
        else:
            j += 1
    return indices


def _particle_filter(y: np.ndarray, num_particles: int, q: float, r: float) -> np.ndarray:
    """Bootstrap particle filter with systematic resampling.

    Returns weighted-mean state estimates shaped (len(y),).
    """
    n = len(y)
    particles = np.random.randn(num_particles)
    weights = np.ones(num_particles) / num_particles
    estimates = np.zeros(n)
    for k in range(n):
        # Propagate
        particles = particles + np.sqrt(q) * np.random.randn(num_particles)
        # Weight: Gaussian likelihood
        log_w = -0.5 * (y[k] - particles) ** 2 / r
        log_w -= np.max(log_w)
        weights = np.exp(log_w)
        weights /= weights.sum()
        # MMSE estimate
        estimates[k] = float(weights @ particles)
        # Effective sample size — resample if needed
        n_eff = 1.0 / float(np.sum(weights**2))
        if n_eff < num_particles / 2:
            indices = _systematic_resample(weights, num_particles)
            particles = particles[indices]
            weights = np.ones(num_particles) / num_particles
    return estimates


class ParticleFilter(Knot):
    """Particle (bootstrap) filter for nonlinear non-Gaussian systems."""

    _valid_resampling_strategies = frozenset(
        {"multinomial", "stratified", "systematic", "residual"}
    )

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
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        process_noise = 1e-2
        measurement_noise = 1e-1
        filtered = await asyncio.to_thread(
            _particle_filter, x.astype(float), particle_count, process_noise, measurement_noise
        )
        frame = SignalFrame(
            signal_id=f"{signal.frame.signal_id}:particle",
            channel_count=1,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=len(filtered),
        )
        return SignalPayload(frame=frame, data=filtered)
