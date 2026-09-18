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

    Replace ``WeatherForecastPipeline.synthetic_grib_records()`` with bytes decoded
    by ``GribFormat``:

        from pirn.connectors.file_formats.grib_format import GribFormat

        fmt = GribFormat()
        records = await fmt.decode(grib_bytes)   # one record per GRIB message

    Each record has: shortName, name, typeOfLevel, level (int|float),
    stepRange (str), values (float64 numpy array as bytes).

Run with:
    uv run python -m examples.domain_formats.weather_forecast_pipeline
"""

from __future__ import annotations

import hashlib
import random
import struct
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.domain_formats.weather_forecast_pipeline.alert_checker import AlertChecker
from examples.domain_formats.weather_forecast_pipeline.forecast import Forecast
from examples.domain_formats.weather_forecast_pipeline.forecast_assembler import ForecastAssembler
from examples.domain_formats.weather_forecast_pipeline.grib_decoder import GribDecoder
from examples.domain_formats.weather_forecast_pipeline.grib_record import GribRecord
from examples.domain_formats.weather_forecast_pipeline.humidity_processor import HumidityProcessor
from examples.domain_formats.weather_forecast_pipeline.pressure_processor import PressureProcessor
from examples.domain_formats.weather_forecast_pipeline.temperature_processor import (
    TemperatureProcessor,
)
from examples.domain_formats.weather_forecast_pipeline.wind_processor import WindProcessor


class WeatherForecastPipeline:
    """Builds and runs the weather forecast tapestry over a list of regions."""

    _regions: ClassVar[tuple[str, ...]] = (
        "North Atlantic (56°N, 20°W)",
        "Mediterranean Basin (40°N, 15°E)",
        "Siberian High (55°N, 90°E)",
        "Gulf Coast (30°N, 90°W)",
    )

    @staticmethod
    def _rng(region: str, extra: str = "") -> random.Random:
        """Return a deterministic RNG seeded from the region name."""
        key = f"{region}|{extra}"
        seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
        return random.Random(seed)

    @staticmethod
    def _float64_bytes(values: list[float]) -> bytes:
        """Pack a list of values as big-endian float64 bytes, as GRIB carries them."""
        return struct.pack(f">{len(values)}d", *values)

    @classmethod
    def synthetic_grib_records(cls, region: str) -> list[GribRecord]:
        """Return synthetic GRIB records shaped like GribFormat output.

        Covers: 2m temperature (multi-level), mean sea level pressure,
        10m u/v wind components, and 2m relative humidity.
        """
        rng = cls._rng(region)

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
                    values=cls._float64_bytes(values),
                )
            )

        records.append(
            GribRecord(
                short_name="msl",
                name="Mean sea level pressure",
                type_of_level="meanSea",
                level=0.0,
                step_range="0",
                values=cls._float64_bytes([mslp_pa + rng.gauss(0, 50) for _ in range(grid_size)]),
            )
        )

        records.append(
            GribRecord(
                short_name="10u",
                name="10 metre U wind component",
                type_of_level="heightAboveGround",
                level=10.0,
                step_range="0",
                values=cls._float64_bytes([u_wind + rng.gauss(0, 2) for _ in range(grid_size)]),
            )
        )
        records.append(
            GribRecord(
                short_name="10v",
                name="10 metre V wind component",
                type_of_level="heightAboveGround",
                level=10.0,
                step_range="0",
                values=cls._float64_bytes([v_wind + rng.gauss(0, 2) for _ in range(grid_size)]),
            )
        )

        records.append(
            GribRecord(
                short_name="2r",
                name="2 metre relative humidity",
                type_of_level="heightAboveGround",
                level=2.0,
                step_range="0",
                values=cls._float64_bytes([rh + rng.gauss(0, 3) for _ in range(grid_size)]),
            )
        )

        return records

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire decode → four parallel processors → assemble → alert check."""
        with Tapestry(history=history) as t:
            region = Parameter("region", str, _config=KnotConfig(id="region"))
            raw_records = Parameter("records", list, _config=KnotConfig(id="raw_records"))

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

    @classmethod
    async def main(cls) -> None:
        """Run the pipeline once per region and print each forecast report."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        print("\n── Weather Forecast Pipeline ──\n")

        for region in cls._regions:
            records = cls.synthetic_grib_records(region)
            req = RunRequest(parameters={"region": region, "records": records})
            r = await t.run(req)
            if not r.succeeded:
                exc = r.exceptions[0]
                print(f"  FAILED ({exc.knot_id}): {exc.message[:80]}")
                continue
            forecast: Forecast = r.outputs["forecast"]
            print(forecast.report())
            print()
