"""Unit tests for :class:`WaterCutTracker`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.water_cut_tracker import WaterCutTracker
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_OIL = ScadaTimeSeries(sensor_id="oil", sample_interval_sec=60.0)
_WATER = ScadaTimeSeries(sensor_id="water", sample_interval_sec=60.0)


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
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "watercut:oil:water"
