"""Unit tests for :class:`RelativePermeabilityModeler`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.relative_permeability_modeler import (
    RelativePermeabilityModeler,
)
from pirn.domains.oilgas.types.pvt_table import PVTTable

_PVT = PVTTable(fluid_id="f")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, method: str = "corey") -> RelativePermeabilityModeler:
        return RelativePermeabilityModeler(
            pvt=None,  # type: ignore[arg-type]
            method=method,
            _config=KnotConfig(id="rp", validate_io=False),
        )

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(pvt=_PVT, method="bogus")

    async def test_returns_kr_params(self) -> None:
        knot = self._make_knot()
        out = await knot.process(pvt=_PVT, method="corey")
        assert out["fluid_id"] == "f"
        assert out["method"] == "corey"
