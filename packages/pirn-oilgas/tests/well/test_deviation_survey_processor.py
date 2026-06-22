"""Unit tests for :class:`DeviationSurveyProcessor`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.types.deviation_survey import DeviationSurvey
from pirn_oilgas.types.deviation_survey_payload import DeviationSurveyPayload
from pirn_oilgas.well.deviation_survey_processor import DeviationSurveyProcessor

_SURVEY = DeviationSurveyPayload(
    metadata=DeviationSurvey(well_id="W", station_count=5),
    data=np.array([
        [0.0, 0.0, 0.0],
        [100.0, 5.0, 10.0],
        [200.0, 10.0, 15.0],
        [300.0, 12.0, 20.0],
        [400.0, 15.0, 25.0],
    ]),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DeviationSurveyProcessor:
        return DeviationSurveyProcessor(
            survey=None,  # type: ignore[arg-type]
            target_md_step=5.0,
            _config=KnotConfig(id="dp", validate_io=False),
        )

    async def test_rejects_non_numeric_step(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "target_md_step"):
            await knot.process(survey=_SURVEY, target_md_step="x")  # type: ignore[arg-type]

    async def test_rejects_non_positive_step(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(survey=_SURVEY, target_md_step=0.0)

    async def test_returns_survey(self) -> None:
        knot = self._make_knot()
        out = await knot.process(survey=_SURVEY, target_md_step=50.0)
        assert isinstance(out, DeviationSurveyPayload)
        assert out.survey.well_id == "W"
        assert out.stations.shape[1] == 3
