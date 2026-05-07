"""Unit tests for :class:`TankGaugingProcessor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.tank_gauging_processor import TankGaugingProcessor

_GAUGE: dict[str, Any] = {
    "opening_level_in": 100.0,
    "closing_level_in": 200.0,
    "bsw_pct": 5.0,
    "temperature_f": 70.0,
}
_TANK_TABLE: dict[str, float] = {"100": 500.0, "200": 1000.0}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TankGaugingProcessor:
        return TankGaugingProcessor(
            gauge_readings=None,  # type: ignore[arg-type]
            tank_table=_TANK_TABLE,
            bsw_correction_factor=0.0,
            _config=KnotConfig(id="tgp", validate_io=False),
        )

    async def test_rejects_non_dict_tank_table(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "tank_table"):
            await knot.process(
                gauge_readings=_GAUGE,
                tank_table="not_a_dict",  # type: ignore[arg-type]
                bsw_correction_factor=0.5,
            )

    async def test_rejects_out_of_range_bsw_factor(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "bsw_correction_factor"):
            await knot.process(
                gauge_readings=_GAUGE,
                tank_table=_TANK_TABLE,
                bsw_correction_factor=1.5,
            )

    async def test_returns_volumes(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            gauge_readings=_GAUGE,
            tank_table=_TANK_TABLE,
            bsw_correction_factor=0.0,
        )
        assert out["gross_volume_bbl"] == 500.0
        assert "net_oil_bbl" in out
        assert "bsw_adjusted_bbl" in out

    async def test_raises_on_missing_opening_field(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "opening_level_in"):
            await knot.process(
                gauge_readings={"closing_level_in": 200.0, "bsw_pct": 5.0},
                tank_table=_TANK_TABLE,
                bsw_correction_factor=0.0,
            )

    async def test_custom_field_names(self) -> None:
        knot = self._make_knot()
        scada_gauge: dict[str, Any] = {"OPEN_IN": 100.0, "CLOSE_IN": 200.0, "BSW": 5.0}
        out = await knot.process(
            gauge_readings=scada_gauge,
            tank_table=_TANK_TABLE,
            bsw_correction_factor=0.0,
            opening_field="OPEN_IN",
            closing_field="CLOSE_IN",
            bsw_pct_field="BSW",
        )
        assert out["gross_volume_bbl"] == 500.0
