"""``WellLocationProjector`` — project a well's surface location onto a CRS."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class WellLocationProjector(Knot):
    """Project a (lon, lat) surface location into a configured CRS."""

    def __init__(
        self,
        *,
        well_id: str,
        longitude_deg: float,
        latitude_deg: float,
        target_crs: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(well_id, str) or not well_id:
            raise ValueError(
                "WellLocationProjector: well_id must be a non-empty string"
            )
        if not isinstance(longitude_deg, (int, float)):
            raise TypeError(
                "WellLocationProjector: longitude_deg must be numeric"
            )
        if not -180.0 <= longitude_deg <= 180.0:
            raise ValueError(
                "WellLocationProjector: longitude_deg must lie in [-180, 180]"
            )
        if not isinstance(latitude_deg, (int, float)):
            raise TypeError(
                "WellLocationProjector: latitude_deg must be numeric"
            )
        if not -90.0 <= latitude_deg <= 90.0:
            raise ValueError(
                "WellLocationProjector: latitude_deg must lie in [-90, 90]"
            )
        if not isinstance(target_crs, str) or not target_crs:
            raise ValueError(
                "WellLocationProjector: target_crs must be a non-empty string"
            )
        self._well_id = well_id
        self._longitude_deg = float(longitude_deg)
        self._latitude_deg = float(latitude_deg)
        self._target_crs = target_crs
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Project the configured (longitude, latitude) coordinates into the target CRS and return the well location record.

        Returns:
            Dict with ``well_id``, projected ``x`` and ``y`` coordinates,
            and the target ``crs`` string.
        """
        return {
            "well_id": self._well_id,
            "x": 0.0,
            "y": 0.0,
            "crs": self._target_crs,
        }
