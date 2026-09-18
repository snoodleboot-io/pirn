"""``VelocityModel`` — interval and RMS velocities derived from a survey.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VelocityModel:
    interval_velocities: list[tuple[float, float]]
    vrms_surface: float
    vrms_target: float
    two_way_time_ms: float
