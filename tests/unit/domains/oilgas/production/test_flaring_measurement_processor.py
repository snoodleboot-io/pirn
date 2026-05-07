"""Unit tests for :class:`FlaringMeasurementProcessor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.flaring_measurement_processor import (
    FlaringMeasurementProcessor,
)

_MEASUREMENTS: list[dict[str, Any]] = [
    {"start_iso": "2026-01-01T00:00:00Z", "end_iso": "2026-01-01T06:00:00Z", "flow_rate_mmscfd": 2.0},
    {"start_iso": "2026-01-02T00:00:00Z", "end_iso": "2026-01-02T03:00:00Z", "flow_rate_mmscfd": 1.0},
]
_COMPOSITION: dict[str, float] = {"co2": 0.05, "ch4": 0.85}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FlaringMeasurementProcessor:
        return FlaringMeasurementProcessor(
            measurements=None,  # type: ignore[arg-type]
            gas_composition=_COMPOSITION,
            efficiency_factor=0.98,
            _config=KnotConfig(id="fp", validate_io=False),
        )

    async def test_rejects_invalid_efficiency_factor(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "efficiency_factor"):
            await knot.process(
                measurements=_MEASUREMENTS,
                gas_composition=_COMPOSITION,
                efficiency_factor=0.0,
            )

    async def test_rejects_non_dict_composition(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "gas_composition"):
            await knot.process(
                measurements=_MEASUREMENTS,
                gas_composition="not_a_dict",  # type: ignore[arg-type]
                efficiency_factor=0.98,
            )

    async def test_returns_flaring_summary(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            measurements=_MEASUREMENTS,
            gas_composition=_COMPOSITION,
            efficiency_factor=0.98,
        )
        assert out["event_count"] == 2
        assert isinstance(out["total_flared_mmscf"], float)
        assert isinstance(out["co2_tonnes"], float)

    async def test_raises_on_missing_flow_rate_field(self) -> None:
        knot = self._make_knot()
        bad = [{"start_iso": "2026-01-01T00:00:00Z"}]
        with self.assertRaisesRegex(KeyError, "flow_rate_mmscfd"):
            await knot.process(
                measurements=bad,
                gas_composition=_COMPOSITION,
                efficiency_factor=0.98,
            )

    async def test_raises_on_missing_co2_component(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "co2"):
            await knot.process(
                measurements=_MEASUREMENTS,
                gas_composition={"ch4": 0.95},
                efficiency_factor=0.98,
            )

    async def test_custom_field_names(self) -> None:
        knot = self._make_knot()
        scada_measurements = [{"FLOW_RATE": 2.0}, {"FLOW_RATE": 1.0}]
        custom_composition = {"CO2": 0.05, "CH4": 0.85}
        out = await knot.process(
            measurements=scada_measurements,
            gas_composition=custom_composition,
            efficiency_factor=0.98,
            flow_rate_field="FLOW_RATE",
            co2_component="CO2",
        )
        assert out["total_flared_mmscf"] == 3.0
