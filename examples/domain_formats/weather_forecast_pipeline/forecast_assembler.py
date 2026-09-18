"""``ForecastAssembler`` — combines every analysis into a forecast narrative.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.weather_forecast_pipeline.forecast import Forecast
from examples.domain_formats.weather_forecast_pipeline.humidity_analysis import HumidityAnalysis
from examples.domain_formats.weather_forecast_pipeline.pressure_analysis import PressureAnalysis
from examples.domain_formats.weather_forecast_pipeline.temperature_analysis import (
    TemperatureAnalysis,
)
from examples.domain_formats.weather_forecast_pipeline.wind_analysis import WindAnalysis


class ForecastAssembler(Knot):
    """Combines all analysis outputs into a coherent forecast narrative."""

    async def process(
        self,
        region: str,
        temperature: TemperatureAnalysis,
        pressure: PressureAnalysis,
        wind: WindAnalysis,
        humidity: HumidityAnalysis,
        **_: Any,
    ) -> Forecast:
        parts: list[str] = []
        t = temperature.surface_celsius
        if t >= 30:
            parts.append("hot")
        elif t >= 20:
            parts.append("warm")
        elif t >= 10:
            parts.append("mild")
        elif t >= 0:
            parts.append("cold")
        else:
            parts.append("freezing")

        if humidity.precipitation_probability_pct >= 70:
            parts.append("wet")
        elif humidity.precipitation_probability_pct >= 40:
            parts.append("unsettled")
        else:
            parts.append("dry")

        parts.append(wind.beaufort_label.lower())

        summary = f"{', '.join(parts).capitalize()} conditions"

        alerts: list[str] = []
        if wind.max_gust_ms >= 28:
            alerts.append(f"WIND WARNING: gusts {wind.max_gust_ms:.0f} m/s")
        if temperature.surface_celsius <= -10:
            alerts.append(f"FROST ALERT: {temperature.surface_celsius:.1f}°C")
        if temperature.surface_celsius >= 35:
            alerts.append(f"HEAT ALERT: {temperature.surface_celsius:.1f}°C")
        if humidity.precipitation_probability_pct >= 80:
            alerts.append("HEAVY RAIN LIKELY")
        if pressure.surface_hpa < 980:
            alerts.append(f"DEEP LOW: {pressure.surface_hpa:.0f} hPa")

        return Forecast(
            region=region,
            valid_time="2026-05-02T12:00Z",
            temperature=temperature,
            pressure=pressure,
            wind=wind,
            humidity=humidity,
            summary=summary,
            alerts=alerts,
        )
