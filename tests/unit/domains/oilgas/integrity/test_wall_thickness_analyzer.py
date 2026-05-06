"""Unit tests for :class:`WallThicknessAnalyzer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.integrity.wall_thickness_analyzer import (
    WallThicknessAnalyzer,
)

_PIG_RUN: dict[str, Any] = {"feature_count": 5, "longest_anomaly_in": 1.0}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, nominal: float = 0.5, minimum: float = 0.25) -> WallThicknessAnalyzer:
        return WallThicknessAnalyzer(
            pig_run=None,  # type: ignore[arg-type]
            nominal_thickness_in=nominal,
            minimum_allowable_thickness_in=minimum,
            _config=KnotConfig(id="wta", validate_io=False),
        )

    async def test_rejects_non_positive_nominal(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "nominal_thickness_in"):
            await knot.process(
                pig_run=_PIG_RUN, nominal_thickness_in=0.0, minimum_allowable_thickness_in=0.2
            )

    async def test_rejects_min_ge_nominal(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "minimum_allowable_thickness_in"):
            await knot.process(
                pig_run=_PIG_RUN, nominal_thickness_in=0.5, minimum_allowable_thickness_in=0.5
            )

    async def test_returns_assessment(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            pig_run=_PIG_RUN, nominal_thickness_in=0.5, minimum_allowable_thickness_in=0.25
        )
        assert out["min_remaining_in"] == 0.5
        assert out["minimum_allowable_in"] == 0.25
