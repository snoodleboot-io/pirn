"""``CoreAssessmentKnot`` — the required geometry assessment stage.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.geospatial_layer_analysis.core_assessment import CoreAssessment
from examples.domain_formats.geospatial_layer_analysis.geo_feature import GeoFeature


class CoreAssessmentKnot(Knot):
    """Required: geometry validation, centroid, and basic spatial statistics."""

    async def process(self, feature: GeoFeature, **_: Any) -> CoreAssessment:
        coords = feature.coordinates
        geometry_valid = bool(coords)

        if feature.geometry_type == "Point" and coords:
            flat = [coords]
        elif feature.geometry_type in ("Polygon", "LineString") and coords:
            ring = coords[0] if feature.geometry_type == "Polygon" else coords
            flat = ring
        else:
            flat = coords if coords else [[0.0, 0.0]]

        try:
            lons = [c[0] for c in flat]
            lats = [c[1] for c in flat]
            centroid_lon = sum(lons) / len(lons)
            centroid_lat = sum(lats) / len(lats)
        except (TypeError, IndexError):
            centroid_lon, centroid_lat = 0.0, 0.0
            geometry_valid = False

        if feature.geometry_type == "Polygon" and len(flat) >= 3:
            n = len(flat)
            shoelace = sum(
                flat[i][0] * flat[(i + 1) % n][1] - flat[(i + 1) % n][0] * flat[i][1]
                for i in range(n)
            )
            area_ha = abs(shoelace) / 2.0 * (111_000.0**2) / 10_000.0
            perimeter_m = 0.0
            for i in range(n):
                dx = (
                    (flat[(i + 1) % n][0] - flat[i][0])
                    * 111_000.0
                    * math.cos(math.radians(centroid_lat))
                )
                dy = (flat[(i + 1) % n][1] - flat[i][1]) * 111_000.0
                perimeter_m += math.hypot(dx, dy)
        else:
            area_ha = 0.0
            perimeter_m = 0.0

        return CoreAssessment(
            feature_id=feature.feature_id,
            centroid_lon=centroid_lon,
            centroid_lat=centroid_lat,
            area_ha=round(area_ha, 4),
            perimeter_m=round(perimeter_m, 1),
            geometry_valid=geometry_valid,
        )
