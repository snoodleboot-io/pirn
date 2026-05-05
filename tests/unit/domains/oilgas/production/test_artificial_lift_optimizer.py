"""Unit tests for :class:`ArtificialLiftOptimizer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.artificial_lift_optimizer import (
    ArtificialLiftOptimizer,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="prod")


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_lift_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "lift_type"):
            with Tapestry():
                src = _Source(_config=KnotConfig(id="src"))
                ArtificialLiftOptimizer(
                    production=src,
                    lift_type="bogus",
                    _config=KnotConfig(id="al"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_recommendation(self) -> None:
        with Tapestry() as t:
            src = _Source(_config=KnotConfig(id="src"))
            ArtificialLiftOptimizer(
                production=src,
                lift_type="esp",
                _config=KnotConfig(id="al"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["al"]
        assert out["lift_type"] == "esp"
        assert "recommended_setpoint" in out
