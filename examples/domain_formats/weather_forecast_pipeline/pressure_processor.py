"""``PressureProcessor`` — classifies pressure systems and estimates tendency.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.weather_forecast_pipeline.grib_record import GribRecord
from examples.domain_formats.weather_forecast_pipeline.pressure_analysis import PressureAnalysis


class PressureProcessor(Knot):
    """Classifies pressure systems and estimates tendency."""

    async def process(self, grouped: dict[str, list[GribRecord]], **_: Any) -> PressureAnalysis:
        recs = grouped.get("pressure", [])
        if not recs:
            raise ValueError("PressureProcessor: no pressure records")

        vals = recs[0].unpacked_values()
        mean_pa = sum(vals) / len(vals) if vals else 101325.0
        mean_hpa = mean_pa / 100.0

        variance = sum((v / 100 - mean_hpa) ** 2 for v in vals) / max(len(vals), 1)
        tendency_hpa = (variance**0.5 - 5.0) * 0.3

        if mean_hpa >= 1020:
            system = "high pressure (anticyclone)"
        elif mean_hpa >= 1013:
            system = "near-normal"
        elif mean_hpa >= 1000:
            system = "low pressure"
        else:
            system = "depression"

        return PressureAnalysis(
            surface_hpa=round(mean_hpa, 1),
            tendency_hpa_per_hour=round(tendency_hpa, 2),
            system_type=system,
        )
