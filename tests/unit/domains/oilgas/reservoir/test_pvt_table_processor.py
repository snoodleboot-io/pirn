"""Unit tests for :class:`PvtTableProcessor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.pvt_table_processor import PvtTableProcessor
from pirn.domains.oilgas.types.pvt_table import PVTTable
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_fluid_id(self) -> None:
        with pytest.raises(ValueError, match="fluid_id"):
            PvtTableProcessor(
                fluid_id="",
                pressure_count=10,
                temperature_count=5,
                _config=KnotConfig(id="pp"),
            )

    def test_rejects_non_positive_pressure_count(self) -> None:
        with pytest.raises(ValueError, match="pressure_count"):
            PvtTableProcessor(
                fluid_id="f",
                pressure_count=0,
                temperature_count=5,
                _config=KnotConfig(id="pp"),
            )

    def test_rejects_non_positive_temperature_count(self) -> None:
        with pytest.raises(ValueError, match="temperature_count"):
            PvtTableProcessor(
                fluid_id="f",
                pressure_count=10,
                temperature_count=-1,
                _config=KnotConfig(id="pp"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_pvt_table(self) -> None:
        with Tapestry() as t:
            PvtTableProcessor(
                fluid_id="fluid-A",
                pressure_count=10,
                temperature_count=5,
                _config=KnotConfig(id="pp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pp"]
        assert isinstance(out, PVTTable)
        assert out.fluid_id == "fluid-A"
        assert out.pressure_count == 10
        assert out.temperature_count == 5
