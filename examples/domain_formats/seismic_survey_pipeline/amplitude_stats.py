"""``AmplitudeStats`` — RMS, peak, percentile and dynamic-range amplitude figures.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AmplitudeStats:
    rms_amplitude: float
    peak_amplitude: float
    p10: float
    p90: float
    dynamic_range_db: float
