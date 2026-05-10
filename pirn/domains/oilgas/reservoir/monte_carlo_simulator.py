"""``MonteCarloSimulator`` — Monte-Carlo OOIP / reserves uncertainty stub.

Algorithm:
    1. Receive a deterministic estimate, a positive ``trial_count``, and a
       random ``seed``.
    2. Validate that ``trial_count`` is a positive integer.
    3. Sample uncertain input parameters (e.g. porosity, area) from configured
       distributions.
    4. Run ``trial_count`` forward simulations.
    5. Return the P10, P50, and P90 percentile estimates.

Math:
    For each trial :math:`i`, draw input parameters :math:`\\theta_i` from
    their prior distributions and compute the output:

    $$Q_i = f(\\theta_i)$$

    Percentile estimates:

    $$P_{10} = \\text{quantile}(\\{Q_i\\}, 0.10), \\quad
      P_{50} = \\text{quantile}(\\{Q_i\\}, 0.50), \\quad
      P_{90} = \\text{quantile}(\\{Q_i\\}, 0.90)$$

References:
    - SPE-PRMS-2018, Petroleum Resources Management System (Section 4.3 —
      probabilistic resource estimation).
    - Hammersley, J.M. & Handscomb, D.C. (1964). *Monte Carlo Methods*.
      Methuen & Co., Chapter 1.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

# Lognormal spread representing typical reservoir parameter uncertainty
# (±30% coefficient of variation is a common industry default for P10/P90 range).
_lognormal_sigma = 0.3


class MonteCarloSimulator(Knot):
    """Run a Monte-Carlo simulation over a configured number of trials."""

    def __init__(
        self,
        *,
        deterministic_estimate: Knot,
        trial_count: Knot | int,
        seed: Knot | int = 0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            deterministic_estimate=deterministic_estimate,
            trial_count=trial_count,
            seed=seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        deterministic_estimate: float,
        trial_count: int,
        seed: int = 0,
        **_: Any,
    ) -> dict[str, float]:
        """Run the Monte-Carlo simulation and return P10, P50, and P90 estimates.

        Args:
            deterministic_estimate: Central deterministic value around which
                uncertainty is sampled.
            trial_count: Positive integer number of Monte-Carlo trials.
            seed: Integer random seed for reproducibility (default 0).

        Returns:
            Dict with keys ``p10``, ``p50``, ``p90``, and ``trial_count``.
        """
        if not isinstance(trial_count, int) or trial_count <= 0:
            raise ValueError("MonteCarloSimulator: trial_count must be a positive integer")
        if not isinstance(seed, int):
            raise TypeError("MonteCarloSimulator: seed must be an integer")

        base = float(deterministic_estimate)
        return await asyncio.to_thread(self._run, base, trial_count, seed)

    @staticmethod
    def _run(base: float, trial_count: int, seed: int) -> dict[str, float]:
        rng = np.random.default_rng(seed)
        # Lognormal distribution centred on the deterministic estimate with
        # _lognormal_sigma capturing typical volumetric parameter spread.
        trials = rng.lognormal(
            mean=np.log(max(base, 1e-9)), sigma=_lognormal_sigma, size=trial_count
        )
        return {
            "p10": float(np.percentile(trials, 10)),
            "p50": float(np.percentile(trials, 50)),
            "p90": float(np.percentile(trials, 90)),
            "trial_count": float(trial_count),
        }
