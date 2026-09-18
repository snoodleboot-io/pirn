"""``HumidityProcessor`` — derives dew point, cloud cover and precipitation odds.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.weather_forecast_pipeline.grib_record import GribRecord
from examples.domain_formats.weather_forecast_pipeline.humidity_analysis import HumidityAnalysis
from examples.domain_formats.weather_forecast_pipeline.temperature_analysis import (
    TemperatureAnalysis,
)


class HumidityProcessor(Knot):
    """Derives dew point, cloud cover estimate, and precipitation probability."""

    async def process(
        self, grouped: dict[str, list[GribRecord]], temperature: TemperatureAnalysis, **_: Any
    ) -> HumidityAnalysis:
        recs = grouped.get("humidity", [])
        if not recs:
            raise ValueError("HumidityProcessor: no humidity records")

        vals = recs[0].unpacked_values()
        rh = min(100.0, max(0.0, sum(vals) / len(vals))) if vals else 60.0

        t = temperature.surface_celsius
        dew_point = t - ((100 - rh) / 5.0)
        cloud_cover = min(100.0, rh * 0.9 + (10 if rh > 85 else 0))
        precip_prob = max(0.0, min(100.0, (rh - 60) * 2.5)) if rh > 60 else 0.0

        return HumidityAnalysis(
            relative_humidity_pct=round(rh, 1),
            dew_point_celsius=round(dew_point, 1),
            cloud_cover_pct=round(cloud_cover, 1),
            precipitation_probability_pct=round(precip_prob, 1),
        )
