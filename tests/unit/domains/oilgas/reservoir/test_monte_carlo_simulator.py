"""Unit tests for :class:`MonteCarloSimulator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.reservoir.monte_carlo_simulator import MonteCarloSimulator


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, trial_count: int = 1000) -> MonteCarloSimulator:
        return MonteCarloSimulator(
            deterministic_estimate=None,  # type: ignore[arg-type]
            trial_count=trial_count,
            _config=KnotConfig(id="mc", validate_io=False),
        )

    async def test_rejects_non_positive_trial_count(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "trial_count"):
            await knot.process(deterministic_estimate=100.0, trial_count=0)

    async def test_rejects_non_int_seed(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "seed"):
            await knot.process(deterministic_estimate=100.0, trial_count=10, seed="x")  # type: ignore[arg-type]

    async def test_returns_percentiles(self) -> None:
        knot = self._make_knot()
        out = await knot.process(deterministic_estimate=100.0, trial_count=1000, seed=42)
        assert "p10" in out
        assert "p50" in out
        assert "p90" in out
        # Ordering must hold for any lognormal draw
        assert out["p10"] < out["p50"] < out["p90"]
        # P50 of a lognormal centred on 100 with σ=0.3 is close to 100
        assert 80.0 < out["p50"] < 120.0
