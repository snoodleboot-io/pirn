"""Entry point: ``python -m examples.domain_formats.seismic_survey_pipeline``."""

import asyncio

from examples.domain_formats.seismic_survey_pipeline.seismic_survey_pipeline import (
    SeismicSurveyPipeline,
)

if __name__ == "__main__":
    asyncio.run(SeismicSurveyPipeline.main())
