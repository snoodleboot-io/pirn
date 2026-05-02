"""``MonteCarloSimulator`` — Monte-Carlo OOIP / reserves uncertainty stub."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MonteCarloSimulator(Knot):
    """Run a Monte-Carlo simulation over a configured number of trials."""

    def __init__(
        self,
        *,
        deterministic_estimate: Knot,
        trial_count: int,
        seed: int = 0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(trial_count, int) or trial_count <= 0:
            raise ValueError(
                "MonteCarloSimulator: trial_count must be a positive integer"
            )
        if not isinstance(seed, int):
            raise TypeError(
                "MonteCarloSimulator: seed must be an integer"
            )
        self._trial_count = trial_count
        self._seed = seed
        super().__init__(
            deterministic_estimate=deterministic_estimate, _config=_config, **kwargs
        )

    async def process(
        self, deterministic_estimate: float, **_: Any
    ) -> dict[str, float]:
        base = float(deterministic_estimate)
        return {
            "p10": base * 0.7,
            "p50": base,
            "p90": base * 1.3,
            "trial_count": float(self._trial_count),
        }
