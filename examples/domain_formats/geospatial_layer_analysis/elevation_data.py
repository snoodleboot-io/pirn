"""``ElevationData`` — the optional elevation signal for one feature's extent.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ElevationData:
    feature_id: str
    mean_elevation_m: float
    min_elevation_m: float
    max_elevation_m: float
    slope_pct: float
