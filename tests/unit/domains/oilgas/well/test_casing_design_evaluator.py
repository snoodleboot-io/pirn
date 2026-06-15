"""Unit tests for :class:`CasingDesignEvaluator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.types.well_path_3d import WellPath3D
from pirn_oilgas.well.casing_design_evaluator import CasingDesignEvaluator

_PATH = WellPath3D(well_id="W", point_count=20)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> CasingDesignEvaluator:
        return CasingDesignEvaluator(
            well_path=None,  # type: ignore[arg-type]
            burst_limit_psi=10000.0,
            collapse_limit_psi=8000.0,
            tension_limit_lbf=300000.0,
            _config=KnotConfig(id="cd", validate_io=False),
        )

    async def test_rejects_non_positive_burst(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "burst_limit_psi"):
            await knot.process(
                well_path=_PATH,
                burst_limit_psi=0.0,
                collapse_limit_psi=10000.0,
                tension_limit_lbf=200000.0,
            )

    async def test_returns_evaluation(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            well_path=_PATH,
            burst_limit_psi=10000.0,
            collapse_limit_psi=8000.0,
            tension_limit_lbf=300000.0,
        )
        assert out["well_id"] == "W"
        assert out["passed"] is True
