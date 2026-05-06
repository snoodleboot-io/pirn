"""Unit tests for :class:`DeviationSurveyProcessor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey
from pirn.domains.oilgas.well.deviation_survey_processor import DeviationSurveyProcessor

_SURVEY = DeviationSurvey(well_id="W", station_count=5)


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
        out = await knot.process(survey=_SURVEY, target_md_step=5.0)
        assert isinstance(out, DeviationSurvey)
        assert out.well_id == "W"
