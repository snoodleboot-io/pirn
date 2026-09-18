"""``TemperatureProcessor`` — derives temperature statistics and lapse rate.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.weather_forecast_pipeline.grib_record import GribRecord
from examples.domain_formats.weather_forecast_pipeline.temperature_analysis import (
    TemperatureAnalysis,
)


class TemperatureProcessor(Knot):
    """Derives temperature statistics and lapse rate from multi-level fields."""

    async def process(self, grouped: dict[str, list[GribRecord]], **_: Any) -> TemperatureAnalysis:
        recs = grouped.get("temperature", [])
        if not recs:
            raise ValueError("TemperatureProcessor: no temperature records")

        surface_rec = next((r for r in recs if r.short_name == "2t" or r.level <= 10), recs[0])
        surface_vals = surface_rec.unpacked_values()
        surface_k = sum(surface_vals) / len(surface_vals) if surface_vals else 273.15
        surface_c = surface_k - 273.15

        all_vals = [v for r in recs for v in r.unpacked_values()]
        min_c = min(all_vals) - 273.15
        max_c = max(all_vals) - 273.15
        mean_c = sum(all_vals) / len(all_vals) - 273.15

        upper_rec = max(recs, key=lambda r: r.level)
        if upper_rec is not surface_rec and upper_rec.level > 100:
            upper_vals = upper_rec.unpacked_values()
            upper_k = sum(upper_vals) / len(upper_vals) if upper_vals else 273.15
            height_km = (1013.25 - upper_rec.level) / 120.0
            lapse = (surface_k - upper_k) / height_km if height_km > 0 else 6.5
        else:
            lapse = 6.5

        return TemperatureAnalysis(
            mean_celsius=round(mean_c, 1),
            min_celsius=round(min_c, 1),
            max_celsius=round(max_c, 1),
            surface_celsius=round(surface_c, 1),
            lapse_rate_c_per_km=round(lapse, 2),
        )
