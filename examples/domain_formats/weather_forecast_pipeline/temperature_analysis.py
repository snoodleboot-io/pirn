"""``TemperatureAnalysis`` — surface, range and lapse-rate temperature figures.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TemperatureAnalysis:
    mean_celsius: float
    min_celsius: float
    max_celsius: float
    surface_celsius: float
    lapse_rate_c_per_km: float
