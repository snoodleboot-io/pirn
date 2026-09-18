"""``WindAnalysis`` — wind speed, gusts, direction and Beaufort classification.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WindAnalysis:
    mean_speed_ms: float
    max_gust_ms: float
    direction_deg: float
    beaufort_scale: int
    beaufort_label: str
