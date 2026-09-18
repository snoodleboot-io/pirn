"""``Forecast`` — the assembled forecast for one region, plus its report text.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.domain_formats.weather_forecast_pipeline.humidity_analysis import HumidityAnalysis
from examples.domain_formats.weather_forecast_pipeline.pressure_analysis import PressureAnalysis
from examples.domain_formats.weather_forecast_pipeline.temperature_analysis import (
    TemperatureAnalysis,
)
from examples.domain_formats.weather_forecast_pipeline.wind_analysis import WindAnalysis


@dataclass
class Forecast:
    region: str
    valid_time: str
    temperature: TemperatureAnalysis
    pressure: PressureAnalysis
    wind: WindAnalysis
    humidity: HumidityAnalysis
    summary: str
    alerts: list[str]

    def report(self) -> str:
        t = self.temperature
        p = self.pressure
        w = self.wind
        h = self.humidity
        alert_str = "  ALERTS: " + " | ".join(self.alerts) if self.alerts else "  No alerts"
        return (
            f"[{self.region}] valid {self.valid_time}\n"
            f"  Temp     : {t.surface_celsius:.1f}°C surface · "
            f"range {t.min_celsius:.1f}-{t.max_celsius:.1f}°C · "
            f"lapse {t.lapse_rate_c_per_km:.1f}°C/km\n"
            f"  Pressure : {p.surface_hpa:.0f} hPa ({p.system_type}) · "
            f"tendency {p.tendency_hpa_per_hour:+.1f} hPa/hr\n"
            f"  Wind     : {w.mean_speed_ms:.1f} m/s · "
            f"gusts {w.max_gust_ms:.1f} m/s · "
            f"{w.direction_deg:.0f}° ({w.beaufort_label}, Bft {w.beaufort_scale})\n"
            f"  Humidity : {h.relative_humidity_pct:.0f}% RH · "
            f"dew {h.dew_point_celsius:.1f}°C · "
            f"cloud {h.cloud_cover_pct:.0f}% · "
            f"precip {h.precipitation_probability_pct:.0f}%\n"
            f"  Summary  : {self.summary}\n"
            f"{alert_str}"
        )
