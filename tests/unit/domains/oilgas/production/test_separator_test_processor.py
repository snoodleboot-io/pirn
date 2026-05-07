"""Unit tests for :class:`SeparatorTestProcessor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.separator_test_processor import (
    SeparatorTestProcessor,
)

_TEST_DATA: dict[str, Any] = {
    "oil_rate_bopd": 500.0,
    "gas_rate_mmscfd": 0.5,
    "water_rate_bwpd": 200.0,
    "separator_pressure_psig": 100.0,
    "separator_temp_f": 80.0,
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, separator_stages: int = 2) -> SeparatorTestProcessor:
        return SeparatorTestProcessor(
            test_data=None,  # type: ignore[arg-type]
            separator_stages=separator_stages,
            _config=KnotConfig(id="stp", validate_io=False),
        )

    async def test_rejects_invalid_stages(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "separator_stages"):
            await knot.process(test_data=_TEST_DATA, separator_stages=4)

    async def test_rejects_non_int_stages(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "separator_stages"):
            await knot.process(test_data=_TEST_DATA, separator_stages=2.0)  # type: ignore[arg-type]

    async def test_returns_gor_wor_shrinkage(self) -> None:
        knot = self._make_knot()
        out = await knot.process(test_data=_TEST_DATA, separator_stages=2)
        assert "gor_scf_bbl" in out
        assert "wor_bbl_bbl" in out
        assert "oil_shrinkage_factor" in out
        assert out["gor_scf_bbl"] > 0.0

    async def test_raises_on_missing_oil_rate_field(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "oil_rate_bopd"):
            await knot.process(
                test_data={"gas_rate_mmscfd": 0.5, "water_rate_bwpd": 200.0},
                separator_stages=2,
            )

    async def test_custom_field_names(self) -> None:
        knot = self._make_knot()
        scada_data: dict[str, Any] = {"OIL": 500.0, "GAS": 0.5, "WATER": 200.0}
        out = await knot.process(
            test_data=scada_data,
            separator_stages=2,
            oil_rate_field="OIL",
            gas_rate_field="GAS",
            water_rate_field="WATER",
        )
        assert "gor_scf_bbl" in out
