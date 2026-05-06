"""Unit tests for :class:`ProductionRateNormalizer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.production_rate_normalizer import (
    ProductionRateNormalizer,
)

_MEASUREMENTS: list[dict[str, Any]] = [
    {"rate_bopd": 500.0, "wellhead_pressure_psia": 100.0, "wellhead_temp_f": 120.0},
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ProductionRateNormalizer:
        return ProductionRateNormalizer(
            measurements=None,  # type: ignore[arg-type]
            reference_pressure_psia=14.7,
            reference_temp_f=60.0,
            _config=KnotConfig(id="prn", validate_io=False),
        )

    async def test_rejects_non_positive_pressure(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "reference_pressure_psia"):
            await knot.process(
                measurements=_MEASUREMENTS,
                reference_pressure_psia=0.0,
                reference_temp_f=60.0,
            )

    async def test_returns_normalized_rates(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            measurements=_MEASUREMENTS,
            reference_pressure_psia=14.7,
            reference_temp_f=60.0,
        )
        assert isinstance(out, list)
        assert len(out) == 1
        assert "normalized_rate_bopd" in out[0]
