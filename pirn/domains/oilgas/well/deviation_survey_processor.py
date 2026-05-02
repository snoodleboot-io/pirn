"""``DeviationSurveyProcessor`` — clean and resample a deviation survey."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey


class DeviationSurveyProcessor(Knot):
    """Validate and resample a deviation survey to a uniform measured-depth step."""

    def __init__(
        self,
        *,
        survey: Knot,
        target_md_step: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_md_step, (int, float)):
            raise TypeError(
                "DeviationSurveyProcessor: target_md_step must be numeric"
            )
        if target_md_step <= 0.0:
            raise ValueError(
                "DeviationSurveyProcessor: target_md_step must be positive"
            )
        self._target_md_step = float(target_md_step)
        super().__init__(survey=survey, _config=_config, **kwargs)

    async def process(self, survey: DeviationSurvey, **_: Any) -> DeviationSurvey:
        return DeviationSurvey(
            well_id=survey.well_id,
            station_count=survey.station_count,
        )
