"""Unit tests for :class:`GasOilRatioCalculator`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.gas_oil_ratio_calculator import GasOilRatioCalculator
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_OIL = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="oil", sample_count=10, sample_interval_sec=60.0),
    data=np.full(10, 500.0),
)
_GAS = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="gas", sample_count=10, sample_interval_sec=60.0),
    data=np.full(10, 1000.0),
)


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
        assert isinstance(out, ScadaPayload)
        assert out.series.sensor_id == "gor:oil:gas"
