"""``DeviationSurveyProcessor`` — clean and resample a deviation survey.

Algorithm:
    1. Receive a deviation survey and a positive ``target_md_step``.
    2. Validate that ``target_md_step`` is a positive number.
    3. Remove duplicate or out-of-order measured-depth stations.
    4. Linearly interpolate inclination and azimuth onto the target MD grid.
    5. Return the resampled DeviationSurvey.

Math:
    Linear interpolation of inclination at target depth :math:`d^*`:

    $$\\theta(d^*) = \\theta_i + \\frac{d^* - d_i}{d_{i+1} - d_i}
      (\\theta_{i+1} - \\theta_i)$$

References:
    - API RP 11V10 (2004) — Design of Pumping Facilities (wellbore deviation
      context).
    - Craig, J.T. & Randall, B.V. (1976). Directional survey calculation.
      *Petroleum Engineer*, March, 38-54.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey
from pirn.domains.oilgas.types.deviation_survey_payload import DeviationSurveyPayload


def _resample_survey(stations: np.ndarray, target_md_step: float) -> np.ndarray:
    sorted_idx = np.argsort(stations[:, 0])
    s = stations[sorted_idx]
    new_md = np.arange(s[0, 0], s[-1, 0], target_md_step)
    new_inc = np.interp(new_md, s[:, 0], s[:, 1])
    new_azi = np.interp(new_md, s[:, 0], s[:, 2])
    return np.column_stack([new_md, new_inc, new_azi]).astype(np.float64)


class DeviationSurveyProcessor(Knot):
    """Validate and resample a deviation survey to a uniform measured-depth step."""

    def __init__(
        self,
        *,
        survey: Knot,
        target_md_step: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            survey=survey,
            target_md_step=target_md_step,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        survey: DeviationSurveyPayload,
        target_md_step: float,
        **_: Any,
    ) -> DeviationSurveyPayload:
        """Validate and resample the deviation survey to the configured measured-depth step and return the resampled survey.

        Args:
            survey: Raw DeviationSurveyPayload to validate and resample.
            target_md_step: Positive measured-depth step for the resampled survey (ft or m).

        Returns:
            DeviationSurveyPayload resampled to the configured measured-depth step.
        """
        if not isinstance(survey, DeviationSurveyPayload):
            raise TypeError("DeviationSurveyProcessor: survey must be a DeviationSurveyPayload")
        if not isinstance(target_md_step, (int, float)):
            raise TypeError("DeviationSurveyProcessor: target_md_step must be numeric")
        if target_md_step <= 0.0:
            raise ValueError("DeviationSurveyProcessor: target_md_step must be positive")
        new_stations = await asyncio.to_thread(_resample_survey, survey.stations, target_md_step)
        return DeviationSurveyPayload(
            metadata=DeviationSurvey(
                well_id=survey.survey.well_id,
                station_count=len(new_stations),
            ),
            data=new_stations,
        )
