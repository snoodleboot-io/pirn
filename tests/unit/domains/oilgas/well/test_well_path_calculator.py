"""Unit tests for :class:`WellPathCalculator`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey
from pirn.domains.oilgas.types.well_path_3d import WellPath3D
from pirn.domains.oilgas.well.well_path_calculator import WellPathCalculator
from pirn.tapestry import Tapestry


class _SurveySource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DeviationSurvey:
        return DeviationSurvey(well_id="W", station_count=10)


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            with Tapestry():
                source = _SurveySource(_config=KnotConfig(id="src"))
                WellPathCalculator(
                    survey=source,
                    method="bogus",
                    _config=KnotConfig(id="wp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_well_path(self) -> None:
        with Tapestry() as t:
            source = _SurveySource(_config=KnotConfig(id="src"))
            WellPathCalculator(
                survey=source,
                method="minimum_curvature",
                _config=KnotConfig(id="wp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["wp"]
        assert isinstance(out, WellPath3D)
        assert out.well_id == "W"
        assert out.point_count == 10
