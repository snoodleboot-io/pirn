"""Unit tests for :class:`PvtTableProcessor`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.pvt_table_processor import PvtTableProcessor
from pirn.domains.oilgas.types.pvt_table import PVTTable


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(
        self,
        fluid_id: str = "fluid-A",
        pressure_count: int = 10,
        temperature_count: int = 5,
    ) -> PvtTableProcessor:
        return PvtTableProcessor(
            fluid_id=fluid_id,
            pressure_count=pressure_count,
            temperature_count=temperature_count,
            _config=KnotConfig(id="pp"),
        )

    async def test_rejects_empty_fluid_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "fluid_id"):
            await knot.process(fluid_id="", pressure_count=10, temperature_count=5)

    async def test_rejects_non_positive_pressure_count(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "pressure_count"):
            await knot.process(fluid_id="f", pressure_count=0, temperature_count=5)

    async def test_rejects_non_positive_temperature_count(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "temperature_count"):
            await knot.process(fluid_id="f", pressure_count=10, temperature_count=-1)

    async def test_returns_pvt_table(self) -> None:
        knot = self._make_knot()
        out = await knot.process(fluid_id="fluid-A", pressure_count=10, temperature_count=5)
        assert isinstance(out, PVTTable)
        assert out.fluid_id == "fluid-A"
        assert out.pressure_count == 10
        assert out.temperature_count == 5
