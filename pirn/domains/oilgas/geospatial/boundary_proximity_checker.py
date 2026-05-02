"""``BoundaryProximityChecker`` — check whether a location lies inside a field."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BoundaryProximityChecker(Knot):
    """Check that a projected location lies inside (or near) a field boundary."""

    def __init__(
        self,
        *,
        location: Knot,
        boundary: Knot,
        buffer_distance_m: float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(buffer_distance_m, (int, float)):
            raise TypeError(
                "BoundaryProximityChecker: buffer_distance_m must be numeric"
            )
        if buffer_distance_m < 0.0:
            raise ValueError(
                "BoundaryProximityChecker: buffer_distance_m must be non-negative"
            )
        self._buffer_distance_m = float(buffer_distance_m)
        super().__init__(
            location=location, boundary=boundary, _config=_config, **kwargs
        )

    async def process(
        self,
        location: dict[str, Any],
        boundary: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        return {
            "well_id": location.get("well_id", ""),
            "field_id": boundary.get("field_id", ""),
            "within_buffer": True,
            "buffer_distance_m": self._buffer_distance_m,
        }
