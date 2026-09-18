"""``SuitabilityScorer`` — grades a feature from whichever signals arrived.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.ok import Ok

from examples.domain_formats.geospatial_layer_analysis.core_assessment import CoreAssessment
from examples.domain_formats.geospatial_layer_analysis.elevation_data import ElevationData
from examples.domain_formats.geospatial_layer_analysis.land_cover_data import LandCoverData
from examples.domain_formats.geospatial_layer_analysis.planning_zone import PlanningZone
from examples.domain_formats.geospatial_layer_analysis.suitability_score import SuitabilityScore


class SuitabilityScorer(Knot):
    """Combine all available signals into a suitability score.

    Receives ``Result[T]`` for optional inputs via RECEIVE_ERRORS policy.
    Uses ``isinstance(signal, Ok)`` to check arrival, gracefully skipping
    missing layers.
    """

    async def process(
        self,
        core: Any,
        elevation: Any,
        land_cover: Any,
        zone: Any,
        **_: Any,
    ) -> SuitabilityScore:
        if not isinstance(core, Ok):
            raise RuntimeError(f"core assessment unavailable: {core}")
        core_val: CoreAssessment = core.value

        factors: dict[str, str] = {}
        signals_used: list[str] = ["core"]
        signals_missing: list[str] = []

        score = 0.50
        if core_val.geometry_valid:
            score += 0.05
            factors["geometry"] = "valid"
        else:
            score -= 0.10
            factors["geometry"] = "invalid"

        if 0.5 <= core_val.area_ha <= 50.0:
            score += 0.05
            factors["area"] = f"{core_val.area_ha:.2f} ha (optimal)"
        elif core_val.area_ha > 50.0:
            factors["area"] = f"{core_val.area_ha:.2f} ha (large)"
        else:
            factors["area"] = f"{core_val.area_ha:.2f} ha (small)"

        if isinstance(elevation, Ok):
            signals_used.append("elevation")
            elev: ElevationData = elevation.value
            if elev.slope_pct < 5.0:
                score += 0.08
                factors["slope"] = f"{elev.slope_pct:.1f}% (flat — bonus)"
            elif elev.slope_pct < 15.0:
                score += 0.02
                factors["slope"] = f"{elev.slope_pct:.1f}% (moderate)"
            else:
                score -= 0.08
                factors["slope"] = f"{elev.slope_pct:.1f}% (steep — penalty)"
            factors["elevation"] = f"{elev.mean_elevation_m:.0f} m mean"
        else:
            signals_missing.append("elevation")

        if isinstance(land_cover, Ok):
            signals_used.append("land_cover")
            lc: LandCoverData = land_cover.value
            if lc.impervious_pct > 80.0:
                score -= 0.10
                factors["land_cover"] = (
                    f"{lc.primary_class} ({lc.impervious_pct:.0f}% impervious - penalty)"
                )
            elif lc.impervious_pct < 20.0:
                score += 0.06
                factors["land_cover"] = (
                    f"{lc.primary_class} ({lc.impervious_pct:.0f}% impervious - bonus)"
                )
            else:
                factors["land_cover"] = f"{lc.primary_class} ({lc.impervious_pct:.0f}% impervious)"
        else:
            signals_missing.append("land_cover")

        if isinstance(zone, Ok):
            signals_used.append("planning_zone")
            z: PlanningZone = zone.value
            if z.development_allowed:
                score += 0.07
                factors["zone"] = f"{z.zone_code} — {z.zone_description} (dev allowed)"
            else:
                score -= 0.05
                factors["zone"] = f"{z.zone_code} — {z.zone_description} (dev restricted)"
            if z.zone_code.startswith("I"):
                score -= 0.08
                factors["zone"] += " (industrial — penalty)"
        else:
            signals_missing.append("planning_zone")

        score = round(min(max(score, 0.0), 1.0), 3)
        if score >= 0.75:
            grade = "A"
        elif score >= 0.60:
            grade = "B"
        elif score >= 0.45:
            grade = "C"
        else:
            grade = "D"

        return SuitabilityScore(
            feature_id=core_val.feature_id,
            score=score,
            grade=grade,
            factors=factors,
            signals_used=signals_used,
            signals_missing=signals_missing,
        )
