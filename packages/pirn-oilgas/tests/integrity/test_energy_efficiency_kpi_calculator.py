"""Unit tests for :class:`EnergyEfficiencyKpiCalculator`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.integrity.energy_efficiency_kpi_calculator import (
    EnergyEfficiencyKpiCalculator,
)
from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="s", sample_count=10, sample_interval_sec=3600.0),
    data=np.full(10, 100.0),
)


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
