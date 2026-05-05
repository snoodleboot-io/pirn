"""Unit tests for :class:`ProductionTestValidator`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.production_test_validator import (
    ProductionTestValidator,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="series")


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_oil_max(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_oil_rate_bopd"):
            with Tapestry():
                src = _Source(_config=KnotConfig(id="src"))
                ProductionTestValidator(
                    series=src,
                    max_oil_rate_bopd=0.0,
                    max_gas_rate_mscfd=1000.0,
                    max_water_rate_bwpd=500.0,
                    _config=KnotConfig(id="pv"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_input_series(self) -> None:
        with Tapestry() as t:
            src = _Source(_config=KnotConfig(id="src"))
            ProductionTestValidator(
                series=src,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                _config=KnotConfig(id="pv"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pv"]
        assert isinstance(out, ScadaTimeSeries)
