"""``SurveyReport`` — assembles every analyser output into one ``SurveyResult``.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.seismic_survey_pipeline.amplitude_stats import AmplitudeStats
from examples.domain_formats.seismic_survey_pipeline.frequency_spectrum import FrequencySpectrum
from examples.domain_formats.seismic_survey_pipeline.horizon_pick import HorizonPick
from examples.domain_formats.seismic_survey_pipeline.normalised_survey import NormalisedSurvey
from examples.domain_formats.seismic_survey_pipeline.survey_result import SurveyResult
from examples.domain_formats.seismic_survey_pipeline.velocity_model import VelocityModel


class SurveyReport(Knot):
    """Assembles all analysis outputs into a single ``SurveyResult``."""

    async def process(
        self,
        survey_name: str,
        survey: NormalisedSurvey,
        frequency: FrequencySpectrum,
        amplitude: AmplitudeStats,
        velocity: VelocityModel,
        horizons: list[HorizonPick],
        **_: Any,
    ) -> SurveyResult:
        return SurveyResult(
            survey_name=survey_name,
            n_traces=survey.n_traces,
            frequency=frequency,
            amplitude=amplitude,
            velocity=velocity,
            horizons=horizons,
        )
