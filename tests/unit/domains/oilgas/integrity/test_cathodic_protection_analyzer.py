"""Unit tests for :class:`CathodicProtectionAnalyzer`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.integrity.cathodic_protection_analyzer import (
    CathodicProtectionAnalyzer,
)
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="potential", sample_count=10, sample_interval_sec=3600.0),
    data=np.full(10, -900.0),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, threshold: float = -850.0) -> CathodicProtectionAnalyzer:
        return CathodicProtectionAnalyzer(
            potential_series=None,  # type: ignore[arg-type]
            protection_threshold_mv=threshold,
            _config=KnotConfig(id="cp", validate_io=False),
        )

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "protection_threshold_mv"):
            await knot.process(potential_series=_SERIES, protection_threshold_mv="x")  # type: ignore[arg-type]

    async def test_returns_coverage(self) -> None:
        knot = self._make_knot(threshold=-850.0)
        out = await knot.process(potential_series=_SERIES, protection_threshold_mv=-850.0)
        assert "coverage_fraction" in out
        assert out["threshold_mv"] == -850.0
