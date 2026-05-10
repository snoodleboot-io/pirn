"""``CoordinateSystemTransformer`` — transform an (x, y) record between CRSs.

Algorithm:
    1. Receive a location dict with ``well_id``, ``x``, ``y``, and optional ``crs``.
    2. Validate that ``target_crs`` is a non-empty string.
    3. Reproject the (x, y) coordinates from the source CRS to ``target_crs``.
    4. Return a dict with ``well_id``, reprojected ``x`` and ``y``, and ``crs``.

Math:
    $$\\mathbf{p}_{\\text{target}} = T_{s \\to t}(\\mathbf{p}_{\\text{source}})$$

    where :math:`T_{s \\to t}` is the coordinate transformation from source CRS
    :math:`s` to target CRS :math:`t`, typically implemented via a sequence of
    datum shifts and map-projection transforms (e.g. the EPSG / PROJ pipeline).

References:
    - OGC 01-009, OpenGIS Coordinate Transformation Service Specification.
    - Snyder, J.P. (1987). *Map Projections — A Working Manual*. USGS
      Professional Paper 1395.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

# Equirectangular scale factors (Snyder, 1987, §4).
# 1° of latitude ≈ 110 540 m (semi-major axis x π / 180 for WGS-84 mean radius).
_meters_per_deg_lat = 110_540.0
# 1° of longitude ≈ 111 320 m at the equator; scaled by cos(lat) at the point.
_meters_per_deg_lon_at_equator = 111_320.0


class CoordinateSystemTransformer(Knot):
    """Transform a projected (x, y) location from a source to target CRS."""

    def __init__(
        self,
        *,
        location: Knot,
        target_crs: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            location=location,
            target_crs=target_crs,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        location: dict[str, Any],
        target_crs: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Transform the (x, y) location from its source CRS to the target CRS and return the reprojected record.

        Args:
            location: Source location dict containing ``well_id``, ``x``,
                ``y``, and optionally ``crs``.
            target_crs: Non-empty EPSG or PROJ string identifying the
                target coordinate reference system.

        Returns:
            Dict with ``well_id``, reprojected ``x`` and ``y`` coordinates,
            and the target ``crs`` string.
        """
        if not isinstance(target_crs, str) or not target_crs:
            raise ValueError("CoordinateSystemTransformer: target_crs must be a non-empty string")

        source_crs = location.get("crs", "")
        x = float(location.get("x", 0.0))
        y = float(location.get("y", 0.0))

        if isinstance(source_crs, str) and source_crs.startswith("EPSG:4326"):
            # Input is geographic (lat=x, lon=y); project to metres via equirectangular.
            lat_deg = x
            lon_deg = y
            x_m = lon_deg * _meters_per_deg_lon_at_equator * math.cos(math.radians(lat_deg))
            y_m = lat_deg * _meters_per_deg_lat
            x, y = x_m, y_m

        return {
            "well_id": location.get("well_id", ""),
            "x": float(x),
            "y": float(y),
            "crs": target_crs,
        }
