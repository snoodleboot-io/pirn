"""``VelocityEstimator`` — derives interval and RMS velocities from survey geometry.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.seismic_survey_pipeline.normalised_survey import NormalisedSurvey
from examples.domain_formats.seismic_survey_pipeline.velocity_model import VelocityModel


class VelocityEstimator(Knot):
    """Estimates interval velocities using a simplified Dix inversion.

    A production version would perform semblance analysis on pre-stack
    gathers across offset ranges.  Here we derive velocity from the
    offset range and an assumed reflector model.
    """

    @staticmethod
    def _vrms(t_ms: float, intervals: list[tuple[float, float]], v_surface: float) -> float:
        """Return the RMS velocity down to ``t_ms`` over the given interval model."""
        t_s = t_ms / 1000
        n_layers = sum(1 for t, _ in intervals if t / 1000 <= t_s)
        if n_layers == 0:
            return v_surface
        velocities = [v for _, v in intervals[:n_layers]]
        return math.sqrt(sum(v**2 for v in velocities) / len(velocities))

    async def process(self, survey: NormalisedSurvey, **_: Any) -> VelocityModel:
        dt_s = survey.sample_rate_us * 1e-6
        total_time_s = survey.n_samples * dt_s
        target_time_ms = total_time_s * 1000 * 0.6

        v_surface = 1500.0
        v_target = 2200.0
        v_deep = 3000.0

        intervals = [
            (total_time_ms * 0.1, v_surface) for total_time_ms in [total_time_s * 1000]
        ] + [
            (total_time_s * 1000 * 0.4, v_target),
            (total_time_s * 1000 * 0.5, v_deep),
        ]

        return VelocityModel(
            interval_velocities=[(round(t, 0), round(v, 0)) for t, v in intervals],
            vrms_surface=round(self._vrms(50, intervals, v_surface), 0),
            vrms_target=round(self._vrms(target_time_ms, intervals, v_surface), 0),
            two_way_time_ms=round(target_time_ms, 0),
        )
