"""``LandCoverData`` — the optional land cover classification for one feature.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LandCoverData:
    feature_id: str
    primary_class: str
    secondary_class: str | None
    impervious_pct: float
    canopy_pct: float
