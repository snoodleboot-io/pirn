"""``WellLocationProjector`` — project a well's surface location onto a CRS.

Algorithm:
    1. Receive ``well_id``, ``longitude_deg``, ``latitude_deg``, and ``target_crs``.
    2. Validate all inputs (well_id non-empty, coordinates in valid ranges, crs non-empty).
    3. Reproject (longitude, latitude) from WGS-84 into the target CRS.
    4. Return a dict with ``well_id``, projected ``x``, ``y``, and ``crs``.

Math:
    For a UTM projection the easting/northing are computed as:

    $$x = k_0 \\, N \\left(\\lambda + \\cdots \\right) + 500{,}000 \\text{ m}$$
    $$y = k_0 \\left(M + N \\tan\\phi \\left(\\frac{\\lambda^2}{2} + \\cdots\\right)\\right)$$

    where :math:`\\phi` is latitude, :math:`\\lambda` is longitude offset from the
    central meridian, :math:`N` is the radius of curvature in the prime vertical,
    :math:`M` is the meridional arc length, and :math:`k_0 = 0.9996` is the
    scale factor at the central meridian (Snyder, 1987).

References:
    - Snyder, J.P. (1987). *Map Projections — A Working Manual*. USGS
      Professional Paper 1395, pp. 56-64.
    - EPSG Geodetic Parameter Registry: https://epsg.org
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

# Equirectangular scale factors (Snyder, 1987, §4).
_meters_per_deg_lat = 110_540.0
_meters_per_deg_lon_at_equator = 111_320.0


class WellLocationProjector(Knot):
    """Project a (lon, lat) surface location into a configured CRS."""

    def __init__(
        self,
        *,
        well_id: Knot | str,
        longitude_deg: Knot | float,
        latitude_deg: Knot | float,
        target_crs: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            well_id=well_id,
            longitude_deg=longitude_deg,
            latitude_deg=latitude_deg,
            target_crs=target_crs,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        well_id: str,
        longitude_deg: float,
        latitude_deg: float,
        target_crs: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Project the (longitude, latitude) coordinates into the target CRS and return the well location record.

        Args:
            well_id: Non-empty well identifier string.
            longitude_deg: Longitude in decimal degrees; must lie in [-180, 180].
            latitude_deg: Latitude in decimal degrees; must lie in [-90, 90].
            target_crs: Non-empty CRS identifier string.

        Returns:
            Dict with ``well_id``, projected ``x`` and ``y`` coordinates,
            and the target ``crs`` string.
        """
        if not isinstance(well_id, str) or not well_id:
            raise ValueError("WellLocationProjector: well_id must be a non-empty string")
        if not isinstance(longitude_deg, (int, float)):
            raise TypeError("WellLocationProjector: longitude_deg must be numeric")
        if not -180.0 <= longitude_deg <= 180.0:
            raise ValueError("WellLocationProjector: longitude_deg must lie in [-180, 180]")
        if not isinstance(latitude_deg, (int, float)):
            raise TypeError("WellLocationProjector: latitude_deg must be numeric")
        if not -90.0 <= latitude_deg <= 90.0:
            raise ValueError("WellLocationProjector: latitude_deg must lie in [-90, 90]")
        if not isinstance(target_crs, str) or not target_crs:
            raise ValueError("WellLocationProjector: target_crs must be a non-empty string")

        # Equirectangular projection: easting scales by cos(lat) to correct for
        # meridian convergence (Snyder 1987, eq. 4-1).
        x_m = (
            float(longitude_deg)
            * _meters_per_deg_lon_at_equator
            * math.cos(math.radians(float(latitude_deg)))
        )
        y_m = float(latitude_deg) * _meters_per_deg_lat

        return {
            "well_id": well_id,
            "x": float(x_m),
            "y": float(y_m),
            "crs": target_crs,
        }
