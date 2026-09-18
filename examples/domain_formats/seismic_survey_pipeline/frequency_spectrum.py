"""``FrequencySpectrum`` — dominant frequency, bandwidth and SNR of a survey.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrequencySpectrum:
    dominant_hz: float
    bandwidth_hz: float
    peak_power_db: float
    noise_floor_db: float
    signal_to_noise: float
