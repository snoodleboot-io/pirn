"""Unit tests for :class:`PressureTransientAnalyzer`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.pressure_transient_analyzer import (
    PressureTransientAnalyzer,
)

_TEST_DATA: dict[str, Any] = {
    "time_hours": [0.0, 1.0, 2.0, 4.0, 8.0],
    "pressure_psi": [3000.0, 3050.0, 3080.0, 3100.0, 3110.0],
    "flow_rate_bopd": 200.0,
}
_EMPTY_DATA: dict[str, Any] = {
    "time_hours": [],
    "pressure_psi": [],
    "flow_rate_bopd": 100.0,
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> PressureTransientAnalyzer:
        return PressureTransientAnalyzer(
            test_data=None,  # type: ignore[arg-type]
            wellbore_radius_ft=0.328,
            formation_thickness_ft=30.0,
            fluid_viscosity_cp=2.0,
            _config=KnotConfig(id="pta", validate_io=False),
        )

    async def test_rejects_non_positive_radius(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "wellbore_radius_ft"):
            await knot.process(
                test_data=_TEST_DATA,
                wellbore_radius_ft=0.0,
                formation_thickness_ft=30.0,
                fluid_viscosity_cp=2.0,
            )

    async def test_returns_reservoir_params(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            test_data=_TEST_DATA,
            wellbore_radius_ft=0.328,
            formation_thickness_ft=30.0,
            fluid_viscosity_cp=2.0,
        )
        assert "permeability_md" in out
        assert "skin_factor" in out
        assert "wellbore_storage" in out
        assert "pi_bopd_psi" in out

    async def test_raises_on_empty_time_series(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                test_data=_EMPTY_DATA,
                wellbore_radius_ft=0.328,
                formation_thickness_ft=30.0,
                fluid_viscosity_cp=2.0,
            )
