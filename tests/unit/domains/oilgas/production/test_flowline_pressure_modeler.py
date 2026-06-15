"""Unit tests for :class:`FlowlinePressureModeler`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.production.flowline_pressure_modeler import FlowlinePressureModeler
from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="rate", sample_count=10, sample_interval_sec=60.0),
    data=np.full(10, 1000.0),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(
        self,
        pipe_inner_diameter_in: float = 4.0,
        pipe_length_ft: float = 1000.0,
    ) -> FlowlinePressureModeler:
        return FlowlinePressureModeler(
            rate_series=None,  # type: ignore[arg-type]
            pipe_inner_diameter_in=pipe_inner_diameter_in,
            pipe_length_ft=pipe_length_ft,
            _config=KnotConfig(id="fp", validate_io=False),
        )

    async def test_rejects_non_positive_diameter(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "pipe_inner_diameter_in"):
            await knot.process(
                rate_series=_SERIES,
                pipe_inner_diameter_in=0.0,
                pipe_length_ft=1000.0,
            )

    async def test_returns_dp_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            rate_series=_SERIES,
            pipe_inner_diameter_in=4.0,
            pipe_length_ft=1000.0,
        )
        assert isinstance(out, ScadaPayload)
        assert "dp:" in out.series.sensor_id
