"""Unit tests for :class:`ProductionForecaster`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.production_forecaster import ProductionForecaster
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _ParamsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, float]:
        return {"qi": 1000.0, "di_per_year": 0.15, "b": 0.5}


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_months(self) -> None:
        with self.assertRaisesRegex(ValueError, "forecast_months"):
            with Tapestry():
                src = _ParamsSource(_config=KnotConfig(id="src"))
                ProductionForecaster(
                    decline_parameters=src,
                    forecast_months=0,
                    _config=KnotConfig(id="pf"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_forecast_series(self) -> None:
        with Tapestry() as t:
            src = _ParamsSource(_config=KnotConfig(id="src"))
            ProductionForecaster(
                decline_parameters=src,
                forecast_months=24,
                _config=KnotConfig(id="pf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pf"]
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "forecast"
        assert out.sample_count == 24
