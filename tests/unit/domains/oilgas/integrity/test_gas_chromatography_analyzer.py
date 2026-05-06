"""Unit tests for :class:`GasChromatographyAnalyzer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.integrity.gas_chromatography_analyzer import (
    GasChromatographyAnalyzer,
)

_GC_REPORT: dict[str, Any] = {
    "components": [
        {"name": "methane", "area_percent": 90.0},
        {"name": "ethane", "area_percent": 10.0},
    ],
    "total_area": 100.0,
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, normalize: bool = True) -> GasChromatographyAnalyzer:
        return GasChromatographyAnalyzer(
            gc_report=None,  # type: ignore[arg-type]
            normalize_fractions=normalize,
            _config=KnotConfig(id="gc", validate_io=False),
        )

    async def test_rejects_non_bool_normalize(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "normalize_fractions"):
            await knot.process(gc_report=_GC_REPORT, normalize_fractions="yes")  # type: ignore[arg-type]

    async def test_rejects_non_dict_report(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "gc_report"):
            await knot.process(gc_report=[], normalize_fractions=True)  # type: ignore[arg-type]

    async def test_returns_mole_fractions(self) -> None:
        knot = self._make_knot()
        out = await knot.process(gc_report=_GC_REPORT, normalize_fractions=True)
        assert "mole_fractions" in out
        assert "gross_heating_value_btu_scf" in out
        assert "specific_gravity" in out
