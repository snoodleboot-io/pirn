"""Unit tests for :class:`WellPathCalculator`."""

from __future__ import annotations

import unittest
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.types.deviation_survey import DeviationSurvey
from pirn_oilgas.types.deviation_survey_payload import DeviationSurveyPayload
from pirn_oilgas.types.well_path_3d_payload import WellPath3DPayload
from pirn_oilgas.well.well_path_calculator import WellPathCalculator

_STATIONS = np.array([
    [0.0, 0.0, 0.0],
    [100.0, 5.0, 10.0],
    [200.0, 10.0, 15.0],
])


class _SurveySource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DeviationSurveyPayload:
        return DeviationSurveyPayload(
            metadata=DeviationSurvey(well_id="W", station_count=3),
            data=_STATIONS,
        )


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_method(self) -> None:
        k = WellPathCalculator.__new__(WellPathCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "method"):
            await k.process(
                survey=DeviationSurveyPayload(
                    metadata=DeviationSurvey(well_id="W", station_count=1),
                    data=_STATIONS,
                ),
                method="bogus",
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
        assert isinstance(out, WellPath3DPayload)
        assert out.path.well_id == "W"
        assert out.points.shape == (3, 3)
