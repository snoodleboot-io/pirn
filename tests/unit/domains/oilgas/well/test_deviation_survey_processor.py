"""Unit tests for :class:`DeviationSurveyProcessor`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey
from pirn.domains.oilgas.well.deviation_survey_processor import (
    DeviationSurveyProcessor,
)
from pirn.tapestry import Tapestry


class _SurveySource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DeviationSurvey:
        return DeviationSurvey(well_id="W", station_count=5)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_numeric_step(self) -> None:
        with self.assertRaisesRegex(TypeError, "target_md_step"):
            with Tapestry():
                src = _SurveySource(_config=KnotConfig(id="src"))
                DeviationSurveyProcessor(
                    survey=src,
                    target_md_step="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="dp"),
                )

    def test_rejects_non_positive_step(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            with Tapestry():
                src = _SurveySource(_config=KnotConfig(id="src"))
                DeviationSurveyProcessor(
                    survey=src,
                    target_md_step=0.0,
                    _config=KnotConfig(id="dp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_survey(self) -> None:
        with Tapestry() as t:
            src = _SurveySource(_config=KnotConfig(id="src"))
            DeviationSurveyProcessor(
                survey=src,
                target_md_step=5.0,
                _config=KnotConfig(id="dp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["dp"]
        assert isinstance(out, DeviationSurvey)
        assert out.well_id == "W"
