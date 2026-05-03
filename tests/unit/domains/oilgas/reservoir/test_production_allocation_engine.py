"""Unit tests for :class:`ProductionAllocationEngine`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.production_allocation_engine import (
    ProductionAllocationEngine,
)
from pirn.tapestry import Tapestry


class _FieldTotalsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"oil_bopd": 1000.0, "gas_mmscfd": 1.0, "water_bwpd": 500.0}


class _WellTestsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"well_id": "W-1", "test_oil_bopd": 600.0, "test_gas_mmscfd": 0.6, "test_water_bwpd": 300.0},
            {"well_id": "W-2", "test_oil_bopd": 400.0, "test_gas_mmscfd": 0.4, "test_water_bwpd": 200.0},
        ]


class TestConstruction:
    def test_rejects_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="allocation_method"):
            with Tapestry():
                ft = _FieldTotalsSource(_config=KnotConfig(id="ft"))
                wt = _WellTestsSource(_config=KnotConfig(id="wt"))
                ProductionAllocationEngine(
                    field_totals=ft,
                    well_tests=wt,
                    allocation_method="invalid",
                    _config=KnotConfig(id="pae"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_allocates_to_wells(self) -> None:
        with Tapestry() as t:
            ft = _FieldTotalsSource(_config=KnotConfig(id="ft"))
            wt = _WellTestsSource(_config=KnotConfig(id="wt"))
            ProductionAllocationEngine(
                field_totals=ft,
                well_tests=wt,
                allocation_method="ratio",
                _config=KnotConfig(id="pae"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pae"]
        assert isinstance(out, list)
        assert len(out) == 2
        total_oil = sum(w["allocated_oil_bopd"] for w in out)
        assert abs(total_oil - 1000.0) < 0.01
