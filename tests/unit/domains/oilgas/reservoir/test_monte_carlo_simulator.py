"""Unit tests for :class:`MonteCarloSimulator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.monte_carlo_simulator import MonteCarloSimulator


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, trial_count: int = 100) -> MonteCarloSimulator:
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
        out = await knot.process(deterministic_estimate=100.0, trial_count=100)
        assert out["p50"] == 100.0
        assert out["p10"] == 70.0
        assert out["p90"] == 130.0
