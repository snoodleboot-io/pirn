"""Unit tests for :class:`DirectionalDrillingPlanner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.well_path_3d import WellPath3D
from pirn.domains.oilgas.well.directional_drilling_planner import DirectionalDrillingPlanner

_PATH = WellPath3D(well_id="W", point_count=20)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DirectionalDrillingPlanner:
        return DirectionalDrillingPlanner(
            current_path=None,  # type: ignore[arg-type]
            target_x=100.0,
            target_y=200.0,
            target_z=2500.0,
            max_dogleg_deg_per_30m=3.0,
            _config=KnotConfig(id="d", validate_io=False),
        )

    async def test_rejects_non_numeric_target(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "target_x"):
            await knot.process(
                current_path=_PATH,
                target_x="x",  # type: ignore[arg-type]
                target_y=0.0,
                target_z=0.0,
                max_dogleg_deg_per_30m=2.0,
            )

    async def test_rejects_non_positive_dogleg(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "max_dogleg"):
            await knot.process(
                current_path=_PATH,
                target_x=0.0,
                target_y=0.0,
                target_z=0.0,
                max_dogleg_deg_per_30m=0.0,
            )

    async def test_returns_well_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            current_path=_PATH,
            target_x=100.0,
            target_y=200.0,
            target_z=2500.0,
            max_dogleg_deg_per_30m=3.0,
        )
        assert isinstance(out, WellPath3D)
        assert out.well_id == "W"
