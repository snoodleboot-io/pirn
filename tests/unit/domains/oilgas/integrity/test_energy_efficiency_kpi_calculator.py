"""Unit tests for :class:`EnergyEfficiencyKpiCalculator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.integrity.energy_efficiency_kpi_calculator import (
    EnergyEfficiencyKpiCalculator,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaTimeSeries(sensor_id="s")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> EnergyEfficiencyKpiCalculator:
        return EnergyEfficiencyKpiCalculator(
            energy_consumption=None,  # type: ignore[arg-type]
            production=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="ek", validate_io=False),
        )

    async def test_returns_kpi_dict(self) -> None:
        knot = self._make_knot()
        out = await knot.process(energy_consumption=_SERIES, production=_SERIES)
        assert "kwh_per_boe" in out
        assert "energy_intensity_index" in out
