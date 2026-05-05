"""Unit tests for :class:`DirectionalDrillingPlanner`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.well_path_3d import WellPath3D
from pirn.domains.oilgas.well.directional_drilling_planner import (
    DirectionalDrillingPlanner,
)
from pirn.tapestry import Tapestry


class _PathSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> WellPath3D:
        return WellPath3D(well_id="W", point_count=20)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_numeric_target(self) -> None:
        with self.assertRaisesRegex(TypeError, "target_x"):
            with Tapestry():
                source = _PathSource(_config=KnotConfig(id="src"))
                DirectionalDrillingPlanner(
                    current_path=source,
                    target_x="x",  # type: ignore[arg-type]
                    target_y=0.0,
                    target_z=0.0,
                    max_dogleg_deg_per_30m=2.0,
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_non_positive_dogleg(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_dogleg"):
            with Tapestry():
                source = _PathSource(_config=KnotConfig(id="src"))
                DirectionalDrillingPlanner(
                    current_path=source,
                    target_x=0.0,
                    target_y=0.0,
                    target_z=0.0,
                    max_dogleg_deg_per_30m=0.0,
                    _config=KnotConfig(id="d"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_well_path(self) -> None:
        with Tapestry() as t:
            source = _PathSource(_config=KnotConfig(id="src"))
            DirectionalDrillingPlanner(
                current_path=source,
                target_x=100.0,
                target_y=200.0,
                target_z=2500.0,
                max_dogleg_deg_per_30m=3.0,
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, WellPath3D)
