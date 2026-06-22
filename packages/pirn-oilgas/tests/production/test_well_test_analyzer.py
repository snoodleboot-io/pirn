"""Unit tests for :class:`WellTestAnalyzer`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.production.well_test_analyzer import WellTestAnalyzer
from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="p", sample_count=10, sample_interval_sec=3600.0),
    data=np.linspace(3000.0, 3100.0, 10),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, method: str = "horner") -> WellTestAnalyzer:
        return WellTestAnalyzer(
            pressure_series=None,  # type: ignore[arg-type]
            method=method,
            _config=KnotConfig(id="wt", validate_io=False),
        )

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(pressure_series=_SERIES, method="bogus")

    async def test_returns_perm_skin(self) -> None:
        knot = self._make_knot()
        out = await knot.process(pressure_series=_SERIES, method="horner")
        assert "permeability_md" in out
        assert "skin" in out
