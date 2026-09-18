"""``CoreAssessment`` — geometry validity, centroid and basic spatial statistics.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoreAssessment:
    feature_id: str
    centroid_lon: float
    centroid_lat: float
    area_ha: float
    perimeter_m: float
    geometry_valid: bool
