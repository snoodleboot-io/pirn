"""``GribRecord`` — one GRIB message as emitted by ``GribFormat.decode()``.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class GribRecord:
    """Matches the record schema emitted by ``GribFormat.decode()``."""

    short_name: str
    name: str
    type_of_level: str
    level: float
    step_range: str
    values: bytes

    def unpacked_values(self) -> list[float]:
        """Decode the big-endian float64 payload into a list of values."""
        n = len(self.values) // 8
        if n == 0:
            return []
        return list(struct.unpack(f">{n}d", self.values))
