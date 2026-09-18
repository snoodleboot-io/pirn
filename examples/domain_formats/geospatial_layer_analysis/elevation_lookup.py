"""``ElevationLookup`` — the optional elevation enrichment stage.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

import random
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.geospatial_layer_analysis.elevation_data import ElevationData
from examples.domain_formats.geospatial_layer_analysis.geo_feature import GeoFeature


class ElevationLookup(Knot):
    """Optional: query elevation service for the feature's extent.

    Raises RuntimeError for ~30 % of features (offshore or remote parcels
    where the elevation tile is unavailable).
    """

    async def process(self, feature: GeoFeature, **_: Any) -> ElevationData:
        rng = random.Random(feature.feature_id + "elev")
        if rng.random() < 0.30:
            raise RuntimeError("elevation service unavailable")
        base = rng.uniform(10.0, 600.0)
        spread = rng.uniform(2.0, 80.0)
        slope = rng.uniform(0.5, 35.0)
        return ElevationData(
            feature_id=feature.feature_id,
            mean_elevation_m=round(base, 1),
            min_elevation_m=round(base - spread * 0.6, 1),
            max_elevation_m=round(base + spread * 0.4, 1),
            slope_pct=round(slope, 1),
        )
