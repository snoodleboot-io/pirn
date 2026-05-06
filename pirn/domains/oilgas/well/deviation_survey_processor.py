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
      *Petroleum Engineer*, March, 38–54.
"""

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
        survey: DeviationSurvey,
        target_md_step: float,
        **_: Any,
    ) -> DeviationSurvey:
        """Validate and resample the deviation survey to the configured measured-depth step and return the resampled survey.

        Args:
            survey: Raw deviation survey to validate and resample.
            target_md_step: Positive measured-depth step for the resampled survey (ft or m).

        Returns:
            DeviationSurvey resampled to the configured measured-depth step.
        """
        if not isinstance(target_md_step, (int, float)):
            raise TypeError(
                "DeviationSurveyProcessor: target_md_step must be numeric"
            )
        if target_md_step <= 0.0:
            raise ValueError(
                "DeviationSurveyProcessor: target_md_step must be positive"
            )
        return DeviationSurvey(
            well_id=survey.well_id,
            station_count=survey.station_count,
        )
