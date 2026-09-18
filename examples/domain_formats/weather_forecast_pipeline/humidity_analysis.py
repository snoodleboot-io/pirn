"""``HumidityAnalysis`` — humidity, dew point, cloud cover and precipitation odds.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HumidityAnalysis:
    relative_humidity_pct: float
    dew_point_celsius: float
    cloud_cover_pct: float
    precipitation_probability_pct: float
