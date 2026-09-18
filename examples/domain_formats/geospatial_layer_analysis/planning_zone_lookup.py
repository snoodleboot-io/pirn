"""``PlanningZoneLookup`` — the optional planning zone enrichment stage.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

import random
from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.domain_formats.geospatial_layer_analysis.geo_feature import GeoFeature
from examples.domain_formats.geospatial_layer_analysis.planning_zone import PlanningZone


class PlanningZoneLookup(Knot):
    """Optional: fetch the planning zone designation for this feature.

    Raises LookupError for ~20 % of features (unregistered parcels).
    """

    _zones: ClassVar[tuple[tuple[str, str, list[str], bool], ...]] = (
        ("R1", "Residential Low Density", ["housing", "home_office"], True),
        ("R2", "Residential Medium Density", ["housing", "retail_small"], True),
        ("C1", "Commercial Core", ["retail", "office", "hospitality"], True),
        ("A1", "Agricultural", ["farming", "forestry"], False),
        ("GS", "Green Space", ["recreation", "conservation"], False),
        ("I1", "Industrial Light", ["light_industry", "storage"], True),
        ("I2", "Industrial Heavy", ["heavy_industry", "waste"], True),
    )

    async def process(self, feature: GeoFeature, **_: Any) -> PlanningZone:
        rng = random.Random(feature.feature_id + "zone")
        if rng.random() < 0.20:
            raise LookupError(f"zone not found: {feature.feature_id}")
        code, desc, uses, dev = rng.choice(self._zones)
        return PlanningZone(
            feature_id=feature.feature_id,
            zone_code=code,
            zone_description=desc,
            permitted_uses=uses,
            development_allowed=dev,
        )
