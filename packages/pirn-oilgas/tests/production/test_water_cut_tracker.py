"""Unit tests for :class:`WaterCutTracker`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.production.water_cut_tracker import WaterCutTracker
from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries

_OIL = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="oil", sample_count=10, sample_interval_sec=60.0),
    data=np.full(10, 500.0),
)
_WATER = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="water", sample_count=10, sample_interval_sec=60.0),
    data=np.full(10, 200.0),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> WaterCutTracker:
        return WaterCutTracker(
            oil_rate=None,  # type: ignore[arg-type]
            water_rate=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="wc", validate_io=False),
        )

    async def test_returns_water_cut_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(oil_rate=_OIL, water_rate=_WATER)
        assert isinstance(out, ScadaPayload)
        assert out.series.sensor_id == "watercut:oil:water"
