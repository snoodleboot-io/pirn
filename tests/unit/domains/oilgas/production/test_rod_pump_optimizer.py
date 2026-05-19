"""Unit tests for :class:`RodPumpOptimizer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.rod_pump_optimizer import RodPumpOptimizer

_CARD: dict[str, Any] = {
    "surface_load_lbf": [1000.0, 2000.0, 3000.0],
    "surface_position_in": [0.0, 72.0, 144.0],
    "current_spm": 8.0,
    "stroke_length_in": 144.0,
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> RodPumpOptimizer:
        return RodPumpOptimizer(
            dynagraph_card=None,  # type: ignore[arg-type]
            target_fillage_pct=80.0,
            max_spm=10.0,
            _config=KnotConfig(id="rpo", validate_io=False),
        )

    async def test_rejects_invalid_fillage_pct(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "target_fillage_pct"):
            await knot.process(dynagraph_card=_CARD, target_fillage_pct=0.0, max_spm=10.0)

    async def test_rejects_non_positive_max_spm(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "max_spm"):
            await knot.process(dynagraph_card=_CARD, target_fillage_pct=80.0, max_spm=0.0)

    async def test_rejects_missing_current_spm(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "current_spm"):
            await knot.process(
                dynagraph_card={"stroke_length_in": 144.0},
                target_fillage_pct=80.0,
                max_spm=10.0,
            )

    async def test_rejects_missing_stroke_length(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "stroke_length_in"):
            await knot.process(
                dynagraph_card={"current_spm": 8.0},
                target_fillage_pct=80.0,
                max_spm=10.0,
            )

    async def test_returns_recommendation(self) -> None:
        knot = self._make_knot()
        out = await knot.process(dynagraph_card=_CARD, target_fillage_pct=80.0, max_spm=10.0)
        assert "recommended_spm" in out
        assert "recommended_stroke_in" in out
        assert out["fillage_pct"] == 80.0
