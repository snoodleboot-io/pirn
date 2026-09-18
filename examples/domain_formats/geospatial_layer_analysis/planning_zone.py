"""``PlanningZone`` — the optional planning designation for one feature.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanningZone:
    feature_id: str
    zone_code: str
    zone_description: str
    permitted_uses: list[str]
    development_allowed: bool
