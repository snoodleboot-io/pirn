"""``PressureAnalysis`` — surface pressure, tendency and system classification.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PressureAnalysis:
    surface_hpa: float
    tendency_hpa_per_hour: float
    system_type: str
