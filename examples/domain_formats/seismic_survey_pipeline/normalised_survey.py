"""``NormalisedSurvey`` — amplitude-normalised traces plus survey geometry.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NormalisedSurvey:
    n_traces: int
    sample_rate_us: int
    n_samples: int
    traces: list[list[float]]
    cdp_x: list[float]
    cdp_y: list[float]
    offset_range: tuple[float, float]
