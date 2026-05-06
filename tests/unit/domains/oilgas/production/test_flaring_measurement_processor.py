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
