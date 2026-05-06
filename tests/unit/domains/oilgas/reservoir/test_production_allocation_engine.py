"""Unit tests for :class:`ProductionAllocationEngine`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.production_allocation_engine import (
    ProductionAllocationEngine,
)

_FIELD_TOTALS: dict[str, Any] = {"oil_bopd": 1000.0, "gas_mmscfd": 1.0, "water_bwpd": 500.0}
_WELL_TESTS: list[dict[str, Any]] = [
    {"well_id": "W-1", "test_oil_bopd": 600.0, "test_gas_mmscfd": 0.6, "test_water_bwpd": 300.0},
    {"well_id": "W-2", "test_oil_bopd": 400.0, "test_gas_mmscfd": 0.4, "test_water_bwpd": 200.0},
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, allocation_method: str = "ratio") -> ProductionAllocationEngine:
        return ProductionAllocationEngine(
            field_totals=None,  # type: ignore[arg-type]
            well_tests=None,  # type: ignore[arg-type]
            allocation_method=allocation_method,
            _config=KnotConfig(id="pae", validate_io=False),
        )

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "allocation_method"):
            await knot.process(
                field_totals=_FIELD_TOTALS,
                well_tests=_WELL_TESTS,
                allocation_method="invalid",
            )

    async def test_allocates_to_wells(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            field_totals=_FIELD_TOTALS,
            well_tests=_WELL_TESTS,
            allocation_method="ratio",
        )
        assert isinstance(out, list)
        assert len(out) == 2
        total_oil = sum(w["allocated_oil_bopd"] for w in out)
        assert abs(total_oil - 1000.0) < 0.01
