"""Unit tests for :class:`ProductionForecaster`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.production_forecaster import ProductionForecaster
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_PARAMS: dict[str, float] = {"qi": 1000.0, "di_per_year": 0.15, "b": 0.5}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, forecast_months: int = 24) -> ProductionForecaster:
        return ProductionForecaster(
            decline_parameters=None,  # type: ignore[arg-type]
            forecast_months=forecast_months,
            _config=KnotConfig(id="pf", validate_io=False),
        )

    async def test_rejects_non_positive_months(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "forecast_months"):
            await knot.process(decline_parameters=_PARAMS, forecast_months=0)

    async def test_returns_forecast_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(decline_parameters=_PARAMS, forecast_months=24)
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "forecast"
        assert out.sample_count == 24
