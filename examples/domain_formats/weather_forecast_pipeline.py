"""Weather forecast pipeline — fan-out over GRIB meteorological fields.

Decodes a set of synthetic GRIB messages (one per meteorological variable),
routes each to a specialist processor running in parallel, then assembles
a human-readable forecast and raises alerts for severe conditions.

Pipeline shape:

    GribDecoder ──► TemperatureProcessor  ──┐
                ──► PressureProcessor     ──┤
                ──► WindProcessor         ──┼──► ForecastAssembler ──► AlertChecker
                ──► HumidityProcessor     ──┘

Working with real GRIB data:

    Replace ``_synthetic_grib_records()`` with bytes decoded by ``GribFormat``:

        from pirn.domains.connectors.file_formats.grib_format import GribFormat

        fmt = GribFormat()
        records = await fmt.decode(grib_bytes)   # one record per GRIB message

    Each record has: shortName, name, typeOfLevel, level (int|float),
    stepRange (str), values (float64 numpy array as bytes).

Run with:
    uv run python examples/domain_formats/weather_forecast_pipeline.py
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random
import struct
from dataclasses import dataclass
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- data models


@dataclass
class GribRecord:
    """Matches the record schema emitted by ``GribFormat.decode()``."""

    short_name: str
    name: str
    type_of_level: str
    level: float
    step_range: str
    values: bytes


@dataclass
class TemperatureAnalysis:
    mean_celsius: float
    min_celsius: float
    max_celsius: float
    surface_celsius: float
    lapse_rate_c_per_km: float


@dataclass
class PressureAnalysis:
    surface_hpa: float
    tendency_hpa_per_hour: float
    system_type: str


@dataclass
class WindAnalysis:
    mean_speed_ms: float
    max_gust_ms: float
    direction_deg: float
    beaufort_scale: int
    beaufort_label: str


@dataclass
class HumidityAnalysis:
    relative_humidity_pct: float
    dew_point_celsius: float
    cloud_cover_pct: float
    precipitation_probability_pct: float


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
            f"range {t.min_celsius:.1f}–{t.max_celsius:.1f}°C · "
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


# ----------------------------------------------------------------- synthetic data


def _rng(region: str, extra: str = "") -> random.Random:
    key = f"{region}|{extra}"
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _float64_bytes(values: list[float]) -> bytes:
    return struct.pack(f">{len(values)}d", *values)


def _synthetic_grib_records(region: str) -> list[GribRecord]:
    """Return synthetic GRIB records shaped like GribFormat output.

    Covers: 2m temperature (multi-level), mean sea level pressure,
    10m u/v wind components, and 2m relative humidity.
    """
    rng = _rng(region)

    base_temp_k = 273.15 + rng.uniform(-5, 25)
    mslp_pa = rng.uniform(98000, 103000)
    u_wind = rng.uniform(-15, 15)
    v_wind = rng.uniform(-15, 15)
    rh = rng.uniform(40, 95)

    grid_size = 50
    records: list[GribRecord] = []

    for level in [2, 850, 500]:
        temp_k = base_temp_k - (level * 0.006 if level > 2 else 0)
        values = [temp_k + rng.gauss(0, 1) for _ in range(grid_size)]
        records.append(
            GribRecord(
                short_name="2t" if level == 2 else "t",
                name="2 metre temperature" if level == 2 else "Temperature",
                type_of_level="heightAboveGround" if level == 2 else "isobaricInhPa",
                level=float(level),
                step_range="0",
                values=_float64_bytes(values),
            )
        )

    records.append(
        GribRecord(
            short_name="msl",
            name="Mean sea level pressure",
            type_of_level="meanSea",
            level=0.0,
            step_range="0",
            values=_float64_bytes([mslp_pa + rng.gauss(0, 50) for _ in range(grid_size)]),
        )
    )

    records.append(
        GribRecord(
            short_name="10u",
            name="10 metre U wind component",
            type_of_level="heightAboveGround",
            level=10.0,
            step_range="0",
            values=_float64_bytes([u_wind + rng.gauss(0, 2) for _ in range(grid_size)]),
        )
    )
    records.append(
        GribRecord(
            short_name="10v",
            name="10 metre V wind component",
            type_of_level="heightAboveGround",
            level=10.0,
            step_range="0",
            values=_float64_bytes([v_wind + rng.gauss(0, 2) for _ in range(grid_size)]),
        )
    )

    records.append(
        GribRecord(
            short_name="2r",
            name="2 metre relative humidity",
            type_of_level="heightAboveGround",
            level=2.0,
            step_range="0",
            values=_float64_bytes([rh + rng.gauss(0, 3) for _ in range(grid_size)]),
        )
    )

    return records


def _unpack_values(values: bytes) -> list[float]:
    n = len(values) // 8
    if n == 0:
        return []
    return list(struct.unpack(f">{n}d", values))


# ----------------------------------------------------------------- knots


class GribDecoder(Knot):
    """Partitions raw GRIB records by variable type for downstream processors.

    In production, calls ``GribFormat.decode(payload)`` to materialise
    records from raw bytes.  Here it accepts pre-built ``GribRecord`` objects
    and routes them into named groups.
    """

    async def process(
        self, records: list[GribRecord], **_: Any
    ) -> dict[str, list[GribRecord]]:
        grouped: dict[str, list[GribRecord]] = {
            "temperature": [],
            "pressure": [],
            "wind": [],
            "humidity": [],
        }
        for rec in records:
            sn = rec.short_name.lower()
            name = rec.name.lower()
            if sn in ("2t", "t") or "temperature" in name:
                grouped["temperature"].append(rec)
            elif sn in ("msl", "sp") or "pressure" in name:
                grouped["pressure"].append(rec)
            elif sn in ("10u", "10v", "u", "v", "ws", "wg") or "wind" in name:
                grouped["wind"].append(rec)
            elif sn in ("2r", "r", "rh") or "humidity" in name:
                grouped["humidity"].append(rec)
        return grouped


class TemperatureProcessor(Knot):
    """Derives temperature statistics and lapse rate from multi-level fields."""

    async def process(
        self, grouped: dict[str, list[GribRecord]], **_: Any
    ) -> TemperatureAnalysis:
        recs = grouped.get("temperature", [])
        if not recs:
            raise ValueError("TemperatureProcessor: no temperature records")

        surface_rec = next(
            (r for r in recs if r.short_name == "2t" or r.level <= 10), recs[0]
        )
        surface_vals = _unpack_values(surface_rec.values)
        surface_k = sum(surface_vals) / len(surface_vals) if surface_vals else 273.15
        surface_c = surface_k - 273.15

        all_vals = [v for r in recs for v in _unpack_values(r.values)]
        min_c = min(all_vals) - 273.15
        max_c = max(all_vals) - 273.15
        mean_c = sum(all_vals) / len(all_vals) - 273.15

        upper_rec = max(recs, key=lambda r: r.level)
        if upper_rec is not surface_rec and upper_rec.level > 100:
            upper_vals = _unpack_values(upper_rec.values)
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


class PressureProcessor(Knot):
    """Classifies pressure systems and estimates tendency."""

    async def process(
        self, grouped: dict[str, list[GribRecord]], **_: Any
    ) -> PressureAnalysis:
        recs = grouped.get("pressure", [])
        if not recs:
            raise ValueError("PressureProcessor: no pressure records")

        vals = _unpack_values(recs[0].values)
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


class WindProcessor(Knot):
    """Derives mean speed, gust estimate, direction, and Beaufort scale."""

    _BEAUFORT: list[tuple[float, str]] = [
        (0.3, "Calm"), (1.6, "Light air"), (3.4, "Light breeze"),
        (5.5, "Gentle breeze"), (8.0, "Moderate breeze"), (10.8, "Fresh breeze"),
        (13.9, "Strong breeze"), (17.2, "Near gale"), (20.8, "Gale"),
        (24.5, "Severe gale"), (28.5, "Storm"), (32.7, "Violent storm"),
        (float("inf"), "Hurricane"),
    ]

    async def process(
        self, grouped: dict[str, list[GribRecord]], **_: Any
    ) -> WindAnalysis:
        recs = grouped.get("wind", [])
        if not recs:
            raise ValueError("WindProcessor: no wind records")

        u_rec = next((r for r in recs if "u" in r.short_name.lower()), None)
        v_rec = next((r for r in recs if "v" in r.short_name.lower()), None)

        u_vals = _unpack_values(u_rec.values) if u_rec else [0.0]
        v_vals = _unpack_values(v_rec.values) if v_rec else [0.0]

        n = min(len(u_vals), len(v_vals))
        speeds = [math.sqrt(u_vals[i]**2 + v_vals[i]**2) for i in range(n)]
        mean_speed = sum(speeds) / len(speeds) if speeds else 0.0
        max_gust = max(speeds) * 1.5 if speeds else 0.0

        mean_u = sum(u_vals) / len(u_vals)
        mean_v = sum(v_vals) / len(v_vals)
        direction_deg = (270 - math.degrees(math.atan2(mean_v, mean_u))) % 360

        bft = 0
        label = "Calm"
        for threshold, bft_label in enumerate(self._BEAUFORT):
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


class HumidityProcessor(Knot):
    """Derives dew point, cloud cover estimate, and precipitation probability."""

    async def process(
        self, grouped: dict[str, list[GribRecord]], temperature: TemperatureAnalysis, **_: Any
    ) -> HumidityAnalysis:
        recs = grouped.get("humidity", [])
        if not recs:
            raise ValueError("HumidityProcessor: no humidity records")

        vals = _unpack_values(recs[0].values)
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


class AlertChecker(Knot):
    """Final gate — logs severe alerts and passes the forecast through."""

    async def process(self, forecast: Forecast, **_: Any) -> Forecast:
        return forecast


# ----------------------------------------------------------------- tapestry


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        region = Parameter("region", str, _config=KnotConfig(id="region"))
        raw_records = Parameter(
            "records", list, _config=KnotConfig(id="raw_records")
        )

        decoded = GribDecoder(
            records=raw_records,
            _config=KnotConfig(id="decoded"),
        )
        temperature = TemperatureProcessor(
            grouped=decoded,
            _config=KnotConfig(id="temperature"),
        )
        pressure = PressureProcessor(
            grouped=decoded,
            _config=KnotConfig(id="pressure"),
        )
        wind = WindProcessor(
            grouped=decoded,
            _config=KnotConfig(id="wind"),
        )
        humidity = HumidityProcessor(
            grouped=decoded,
            temperature=temperature,
            _config=KnotConfig(id="humidity"),
        )
        assembled = ForecastAssembler(
            region=region,
            temperature=temperature,
            pressure=pressure,
            wind=wind,
            humidity=humidity,
            _config=KnotConfig(id="assembled"),
        )
        AlertChecker(
            forecast=assembled,
            _config=KnotConfig(id="forecast"),
        )
    return t


# ----------------------------------------------------------------- regions


REGIONS = [
    "North Atlantic (56°N, 20°W)",
    "Mediterranean Basin (40°N, 15°E)",
    "Siberian High (55°N, 90°E)",
    "Gulf Coast (30°N, 90°W)",
]


# ----------------------------------------------------------------- main


async def main() -> None:
    # Raw GRIB value bytes in intermediate outputs are not JSON-serialisable;
    # skip history for this example.
    t = build_tapestry(history=None)

    print("\n── Weather Forecast Pipeline ──\n")

    for region in REGIONS:
        records = _synthetic_grib_records(region)
        req = RunRequest(parameters={"region": region, "records": records})
        r = await t.run(req)
        if not r.succeeded:
            exc = r.exceptions[0]
            print(f"  FAILED ({exc.knot_id}): {exc.message[:80]}")
            continue
        forecast: Forecast = r.outputs["forecast"]
        print(forecast.report())
        print()


if __name__ == "__main__":
    asyncio.run(main())
