"""``WindProcessor`` — derives mean speed, gusts, direction and Beaufort scale.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.domain_formats.weather_forecast_pipeline.grib_record import GribRecord
from examples.domain_formats.weather_forecast_pipeline.wind_analysis import WindAnalysis


class WindProcessor(Knot):
    """Derives mean speed, gust estimate, direction, and Beaufort scale."""

    _beaufort: ClassVar[tuple[tuple[float, str], ...]] = (
        (0.3, "Calm"),
        (1.6, "Light air"),
        (3.4, "Light breeze"),
        (5.5, "Gentle breeze"),
        (8.0, "Moderate breeze"),
        (10.8, "Fresh breeze"),
        (13.9, "Strong breeze"),
        (17.2, "Near gale"),
        (20.8, "Gale"),
        (24.5, "Severe gale"),
        (28.5, "Storm"),
        (32.7, "Violent storm"),
        (float("inf"), "Hurricane"),
    )

    async def process(self, grouped: dict[str, list[GribRecord]], **_: Any) -> WindAnalysis:
        recs = grouped.get("wind", [])
        if not recs:
            raise ValueError("WindProcessor: no wind records")

        u_rec = next((r for r in recs if "u" in r.short_name.lower()), None)
        v_rec = next((r for r in recs if "v" in r.short_name.lower()), None)

        u_vals = u_rec.unpacked_values() if u_rec else [0.0]
        v_vals = v_rec.unpacked_values() if v_rec else [0.0]

        n = min(len(u_vals), len(v_vals))
        speeds = [math.sqrt(u_vals[i] ** 2 + v_vals[i] ** 2) for i in range(n)]
        mean_speed = sum(speeds) / len(speeds) if speeds else 0.0
        max_gust = max(speeds) * 1.5 if speeds else 0.0

        mean_u = sum(u_vals) / len(u_vals)
        mean_v = sum(v_vals) / len(v_vals)
        direction_deg = (270 - math.degrees(math.atan2(mean_v, mean_u))) % 360

        bft = 0
        label = "Calm"
        for threshold, bft_label in enumerate(self._beaufort):
            if mean_speed < bft_label[0]:
                label = bft_label[1]
                break
            bft = threshold + 1

        return WindAnalysis(
            mean_speed_ms=round(mean_speed, 1),
            max_gust_ms=round(max_gust, 1),
            direction_deg=round(direction_deg, 0),
            beaufort_scale=bft,
            beaufort_label=label,
        )
