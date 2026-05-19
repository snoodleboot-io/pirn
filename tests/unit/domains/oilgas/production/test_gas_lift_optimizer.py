"""Unit tests for :class:`GasLiftOptimizer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.gas_lift_optimizer import GasLiftOptimizer

_WELL_DATA: dict[str, Any] = {
    "current_injection_mmscfd": 0.5,
    "performance_curve": [
        {"injection_mmscfd": 0.0, "oil_bopd": 200.0},
        {"injection_mmscfd": 0.5, "oil_bopd": 400.0},
        {"injection_mmscfd": 1.0, "oil_bopd": 550.0},
        {"injection_mmscfd": 1.5, "oil_bopd": 580.0},
        {"injection_mmscfd": 2.0, "oil_bopd": 560.0},
    ],
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GasLiftOptimizer:
        return GasLiftOptimizer(
            well_data=None,  # type: ignore[arg-type]
            injection_gas_cost_per_mscf=2.5,
            max_injection_rate_mmscfd=2.0,
            _config=KnotConfig(id="gl", validate_io=False),
        )

    async def test_rejects_non_positive_cost(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "injection_gas_cost_per_mscf"):
            await knot.process(
                well_data=_WELL_DATA,
                injection_gas_cost_per_mscf=0.0,
                max_injection_rate_mmscfd=2.0,
            )

    async def test_rejects_missing_performance_curve(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "performance_curve"):
            await knot.process(
                well_data={"current_injection_mmscfd": 0.5},
                injection_gas_cost_per_mscf=2.5,
                max_injection_rate_mmscfd=2.0,
            )

    async def test_rejects_missing_current_injection(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "current_injection_mmscfd"):
            await knot.process(
                well_data={"performance_curve": []},
                injection_gas_cost_per_mscf=2.5,
                max_injection_rate_mmscfd=2.0,
            )

    async def test_rejects_missing_curve_point_fields(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "injection_mmscfd"):
            await knot.process(
                well_data={"performance_curve": [{"oil_bopd": 400.0}], "current_injection_mmscfd": 0.5},
                injection_gas_cost_per_mscf=2.5,
                max_injection_rate_mmscfd=2.0,
            )

    async def test_returns_optimal_injection(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            well_data=_WELL_DATA,
            injection_gas_cost_per_mscf=2.5,
            max_injection_rate_mmscfd=2.0,
        )
        assert "optimal_injection_mmscfd" in out
        assert "projected_oil_bopd" in out
        assert "incremental_bopd" in out
        assert out["projected_oil_bopd"] > 0.0
