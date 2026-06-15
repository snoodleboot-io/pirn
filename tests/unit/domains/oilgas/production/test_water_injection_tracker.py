"""Unit tests for :class:`WaterInjectionTracker`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.production.water_injection_tracker import WaterInjectionTracker
from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="inj", sample_count=10, sample_interval_sec=60.0),
    data=np.full(10, 100.0),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> WaterInjectionTracker:
        return WaterInjectionTracker(
            injection_rate=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="wi", validate_io=False),
        )

    async def test_returns_cumulative_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(injection_rate=_SERIES)
        assert isinstance(out, ScadaPayload)
        assert "cumulative_inj" in out.series.sensor_id
