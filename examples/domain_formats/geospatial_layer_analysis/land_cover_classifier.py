"""``LandCoverClassifier`` — the optional land cover enrichment stage.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

import random
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.geospatial_layer_analysis.geo_feature import GeoFeature
from examples.domain_formats.geospatial_layer_analysis.land_cover_data import LandCoverData


class LandCoverClassifier(Knot):
    """Optional: classify land cover from a raster tile.

    Raises TimeoutError for ~25 % of features (raster tile not yet cached).
    """

    async def process(self, feature: GeoFeature, **_: Any) -> LandCoverData:
        rng = random.Random(feature.feature_id + "lc")
        if rng.random() < 0.25:
            raise TimeoutError("raster tile timeout")
        classes = ["Grassland", "Cropland", "Forest", "Wetland", "Urban", "Shrubland", "Bare soil"]
        secondary_pool = [None, "Sparse vegetation", "Mixed use", "Transitional"]
        primary = rng.choice(classes)
        secondary = rng.choice(secondary_pool)
        impervious = rng.uniform(0.0, 95.0) if primary == "Urban" else rng.uniform(0.0, 20.0)
        canopy = rng.uniform(30.0, 80.0) if primary == "Forest" else rng.uniform(0.0, 30.0)
        return LandCoverData(
            feature_id=feature.feature_id,
            primary_class=primary,
            secondary_class=secondary,
            impervious_pct=round(impervious, 1),
            canopy_pct=round(canopy, 1),
        )
