"""Unit tests for :class:`GasOilRatioCalculator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.gas_oil_ratio_calculator import (
    GasOilRatioCalculator,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_OIL = ScadaTimeSeries(sensor_id="oil", sample_interval_sec=60.0)
_GAS = ScadaTimeSeries(sensor_id="gas", sample_interval_sec=60.0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GasOilRatioCalculator:
        return GasOilRatioCalculator(
            oil_rate=None,  # type: ignore[arg-type]
            gas_rate=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="gor", validate_io=False),
        )

    async def test_returns_gor_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(oil_rate=_OIL, gas_rate=_GAS)
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "gor:oil:gas"
