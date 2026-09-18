"""``GribDecoder`` — partitions raw GRIB records by variable type.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.weather_forecast_pipeline.grib_record import GribRecord


class GribDecoder(Knot):
    """Partitions raw GRIB records by variable type for downstream processors.

    In production, calls ``GribFormat.decode(payload)`` to materialise
    records from raw bytes.  Here it accepts pre-built ``GribRecord`` objects
    and routes them into named groups.
    """

    async def process(self, records: list[GribRecord], **_: Any) -> dict[str, list[GribRecord]]:
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
