"""Unit tests for :class:`ArtificialLiftOptimizer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.artificial_lift_optimizer import (
    ArtificialLiftOptimizer,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaTimeSeries(sensor_id="prod")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, lift_type: str = "esp") -> ArtificialLiftOptimizer:
        return ArtificialLiftOptimizer(
            production=None,  # type: ignore[arg-type]
            lift_type=lift_type,
            _config=KnotConfig(id="al", validate_io=False),
        )

    async def test_rejects_invalid_lift_type(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "lift_type"):
            await knot.process(production=_SERIES, lift_type="bogus")

    async def test_returns_recommendation(self) -> None:
        knot = self._make_knot(lift_type="esp")
        out = await knot.process(production=_SERIES, lift_type="esp")
        assert out["lift_type"] == "esp"
        assert "recommended_setpoint" in out
