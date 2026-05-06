"""Unit tests for :class:`WaterInjectionTracker`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.water_injection_tracker import (
    WaterInjectionTracker,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaTimeSeries(sensor_id="inj", sample_interval_sec=60.0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> WaterInjectionTracker:
        return WaterInjectionTracker(
            injection_rate=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="wi", validate_io=False),
        )

    async def test_returns_cumulative_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(injection_rate=_SERIES)
        assert isinstance(out, ScadaTimeSeries)
        assert "cumulative_inj" in out.sensor_id
