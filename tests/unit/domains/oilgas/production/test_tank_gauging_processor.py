"""Unit tests for :class:`TankGaugingProcessor`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.tank_gauging_processor import TankGaugingProcessor
from pirn.tapestry import Tapestry


class _GaugeSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "opening_level_in": 100.0,
            "closing_level_in": 200.0,
            "bsw_pct": 5.0,
            "temperature_f": 70.0,
        }


_TANK_TABLE = {"100": 500.0, "200": 1000.0}


class TestConstruction(unittest.TestCase):
    def test_rejects_non_dict_tank_table(self) -> None:
        with self.assertRaisesRegex(TypeError, "tank_table"):
            with Tapestry():
                src = _GaugeSource(_config=KnotConfig(id="src"))
                TankGaugingProcessor(
                    gauge_readings=src,
                    tank_table="not_a_dict",  # type: ignore[arg-type]
                    bsw_correction_factor=0.5,
                    _config=KnotConfig(id="tgp"),
                )

    def test_rejects_out_of_range_bsw_factor(self) -> None:
        with self.assertRaisesRegex(ValueError, "bsw_correction_factor"):
            with Tapestry():
                src = _GaugeSource(_config=KnotConfig(id="src"))
                TankGaugingProcessor(
                    gauge_readings=src,
                    tank_table=_TANK_TABLE,
                    bsw_correction_factor=1.5,
                    _config=KnotConfig(id="tgp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_volumes(self) -> None:
        with Tapestry() as t:
            src = _GaugeSource(_config=KnotConfig(id="src"))
            TankGaugingProcessor(
                gauge_readings=src,
                tank_table=_TANK_TABLE,
                bsw_correction_factor=0.0,
                _config=KnotConfig(id="tgp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["tgp"]
        assert out["gross_volume_bbl"] == 500.0
        assert "net_oil_bbl" in out
        assert "bsw_adjusted_bbl" in out
