"""Unit tests for :class:`MaterialBalanceCalculator`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.material_balance_calculator import (
    MaterialBalanceCalculator,
)
from pirn.domains.oilgas.types.pvt_table import PVTTable
from pirn.tapestry import Tapestry


class _PvtSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> PVTTable:
        return PVTTable(fluid_id="f")


class TestConstruction:
    def test_rejects_negative_cum_oil(self) -> None:
        with pytest.raises(ValueError, match="cumulative_oil_stb"):
            with Tapestry():
                pvt = _PvtSource(_config=KnotConfig(id="src"))
                MaterialBalanceCalculator(
                    pvt=pvt,
                    cumulative_oil_stb=-1.0,
                    cumulative_gas_mscf=0.0,
                    cumulative_water_stb=0.0,
                    average_pressure_psi=2000.0,
                    _config=KnotConfig(id="mb"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_ooip_ogip(self) -> None:
        with Tapestry() as t:
            pvt = _PvtSource(_config=KnotConfig(id="src"))
            MaterialBalanceCalculator(
                pvt=pvt,
                cumulative_oil_stb=10.0,
                cumulative_gas_mscf=20.0,
                cumulative_water_stb=5.0,
                average_pressure_psi=2000.0,
                _config=KnotConfig(id="mb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mb"]
        assert out["ooip_stb"] == 100.0
        assert out["ogip_mscf"] == 200.0
