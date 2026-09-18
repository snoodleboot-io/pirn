"""``GeoFeature`` — one GeoJSON-style feature: geometry plus properties.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GeoFeature:
    feature_id: str
    geometry_type: str
    coordinates: list
    properties: dict = field(default_factory=dict)
