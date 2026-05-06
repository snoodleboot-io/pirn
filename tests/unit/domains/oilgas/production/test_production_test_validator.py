"""Unit tests for :class:`ProductionTestValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.production_test_validator import (
    ProductionTestValidator,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaTimeSeries(sensor_id="series")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ProductionTestValidator:
        return ProductionTestValidator(
            series=None,  # type: ignore[arg-type]
            max_oil_rate_bopd=10000.0,
            max_gas_rate_mscfd=20000.0,
            max_water_rate_bwpd=5000.0,
            _config=KnotConfig(id="pv", validate_io=False),
        )

    async def test_rejects_non_positive_oil_max(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "max_oil_rate_bopd"):
            await knot.process(
                series=_SERIES,
                max_oil_rate_bopd=0.0,
                max_gas_rate_mscfd=1000.0,
                max_water_rate_bwpd=500.0,
            )

    async def test_returns_input_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            series=_SERIES,
            max_oil_rate_bopd=10000.0,
            max_gas_rate_mscfd=20000.0,
            max_water_rate_bwpd=5000.0,
        )
        assert isinstance(out, ScadaTimeSeries)
