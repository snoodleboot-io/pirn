"""Unit tests for :class:`MaterialBalanceCalculator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.material_balance_calculator import (
    MaterialBalanceCalculator,
)
from pirn.domains.oilgas.types.pvt_table import PVTTable

_PVT = PVTTable(fluid_id="f")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> MaterialBalanceCalculator:
        return MaterialBalanceCalculator(
            pvt=None,  # type: ignore[arg-type]
            cumulative_oil_stb=10.0,
            cumulative_gas_mscf=20.0,
            cumulative_water_stb=5.0,
            average_pressure_psi=2000.0,
            _config=KnotConfig(id="mb", validate_io=False),
        )

    async def test_rejects_negative_cum_oil(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "cumulative_oil_stb"):
            await knot.process(
                pvt=_PVT,
                cumulative_oil_stb=-1.0,
                cumulative_gas_mscf=0.0,
                cumulative_water_stb=0.0,
                average_pressure_psi=2000.0,
            )

    async def test_returns_ooip_ogip(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            pvt=_PVT,
            cumulative_oil_stb=10.0,
            cumulative_gas_mscf=20.0,
            cumulative_water_stb=5.0,
            average_pressure_psi=2000.0,
        )
        assert out["ooip_stb"] == 100.0
        assert out["ogip_mscf"] == 200.0
