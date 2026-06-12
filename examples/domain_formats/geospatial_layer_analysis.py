"""Example: Geospatial layer analysis with optional enrichment signals.

A spatial analyst loads a set of GeoJSON features (land parcels / sites),
runs a required core assessment (geometry validation and basic statistics),
then enriches each feature with three optional services:

  * Elevation lookup    — may be unavailable for offshore or remote parcels
  * Land cover class    — requires a raster tile that may timeout
  * Planning zone       — may return 404 for unregistered parcels

The final suitability scorer works with whatever arrived and degrades
gracefully when any optional service is down or absent.

Demonstrates:
- Optional inputs via RECEIVE_ERRORS error policy: a knot can inspect
  whether each parent produced Ok, Err, or Skipped and act accordingly
- Resilient geospatial pipelines: unavailable enrichment layers reduce
  confidence but never block the primary suitability assessment
- The difference between a required signal (core assessment) and
  supplementary signals that improve but are not blocking

Topology:

    feature ──► core_assessment ──────────────────────────────────────────► suitability_score
             ── elevation_lookup  (may fail / unavailable) ───────────────► suitability_score
             ── land_cover_class  (may fail / timeout)     ───────────────► suitability_score
             ── planning_zone     (may fail / not found)   ───────────────► suitability_score

Working with real GeoJSON:
--------------------------
Replace the synthetic features below with data decoded from a real file::

    from pirn.connectors.file_formats.geojson_format import GeoJsonFormat

    fmt = GeoJsonFormat()
    with open("parcels.geojson", "rb") as fh:
        records = fmt.decode(fh.read())

    features = [
        GeoFeature(
            feature_id=r["feature_id"] or f"feat-{i}",
            geometry_type=r["geometry"]["type"],
            coordinates=r["geometry"]["coordinates"],
            properties=r["properties"],
        )
        for i, r in enumerate(records)
    ]

Run with:
    uv run python examples/domain_formats/geospatial_layer_analysis.py
"""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.result import Ok
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class GeoFeature:
    feature_id: str
    geometry_type: str
    coordinates: list
    properties: dict = field(default_factory=dict)


@dataclass
class CoreAssessment:
    feature_id: str
    centroid_lon: float
    centroid_lat: float
    area_ha: float
    perimeter_m: float
    geometry_valid: bool


@dataclass
class ElevationData:
    feature_id: str
    mean_elevation_m: float
    min_elevation_m: float
    max_elevation_m: float
    slope_pct: float


@dataclass
class LandCoverData:
    feature_id: str
    primary_class: str
    secondary_class: str | None
    impervious_pct: float
    canopy_pct: float


@dataclass
class PlanningZone:
    feature_id: str
    zone_code: str
    zone_description: str
    permitted_uses: list[str]
    development_allowed: bool


@dataclass
class SuitabilityScore:
    feature_id: str
    score: float
    grade: str
    factors: dict[str, str]
    signals_used: list[str]
    signals_missing: list[str]


# ----------------------------------------------------------------- knots


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


class PlanningZoneLookup(Knot):
    """Optional: fetch the planning zone designation for this feature.

    Raises LookupError for ~20 % of features (unregistered parcels).
    """

    _ZONES: ClassVar[list[tuple[str, str, list[str], bool]]] = [
        ("R1", "Residential Low Density", ["housing", "home_office"], True),
        ("R2", "Residential Medium Density", ["housing", "retail_small"], True),
        ("C1", "Commercial Core", ["retail", "office", "hospitality"], True),
        ("A1", "Agricultural", ["farming", "forestry"], False),
        ("GS", "Green Space", ["recreation", "conservation"], False),
        ("I1", "Industrial Light", ["light_industry", "storage"], True),
        ("I2", "Industrial Heavy", ["heavy_industry", "waste"], True),
    ]

    async def process(self, feature: GeoFeature, **_: Any) -> PlanningZone:
        rng = random.Random(feature.feature_id + "zone")
        if rng.random() < 0.20:
            raise LookupError(f"zone not found: {feature.feature_id}")
        code, desc, uses, dev = rng.choice(self._ZONES)
        return PlanningZone(
            feature_id=feature.feature_id,
            zone_code=code,
            zone_description=desc,
            permitted_uses=uses,
            development_allowed=dev,
        )


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


# ----------------------------------------------------------------- pipeline


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        feature = Parameter("feature", GeoFeature, _config=KnotConfig(id="feature"))

        core = CoreAssessmentKnot(feature=feature, _config=KnotConfig(id="core"))
        elev = ElevationLookup(feature=feature, _config=KnotConfig(id="elevation"))
        lc = LandCoverClassifier(feature=feature, _config=KnotConfig(id="land_cover"))
        zone = PlanningZoneLookup(feature=feature, _config=KnotConfig(id="zone"))

        SuitabilityScorer(
            core=core,
            elevation=elev,
            land_cover=lc,
            zone=zone,
            _config=KnotConfig(
                id="score",
                error_policy=ErrorPolicy.RECEIVE_ERRORS,
            ),
        )
    return t


# ----------------------------------------------------------------- synthetic data


def _synthetic_features(region: str, n: int) -> list[GeoFeature]:
    """Generate deterministic synthetic GeoJSON-style features for a region."""
    region_centres: dict[str, tuple[float, float]] = {
        "Thames Valley": (-0.9, 51.5),
        "Rhine Delta": (4.9, 51.9),
        "Sacramento Basin": (-121.5, 38.5),
    }
    centre_lon, centre_lat = region_centres.get(region, (0.0, 51.0))
    rng = random.Random(region)
    features: list[GeoFeature] = []

    for i in range(n):
        fid = f"{region.replace(' ', '-').lower()}-{i + 1:03d}"
        lon = centre_lon + rng.uniform(-0.3, 0.3)
        lat = centre_lat + rng.uniform(-0.15, 0.15)
        # Alternate between Point and small Polygon parcels.
        if i % 3 == 0:
            geometry_type = "Point"
            coords: list = [round(lon, 6), round(lat, 6)]
        else:
            d = rng.uniform(0.001, 0.012)  # roughly 100 m - 1 km side
            geometry_type = "Polygon"
            coords = [
                [
                    [round(lon, 6), round(lat, 6)],
                    [round(lon + d, 6), round(lat, 6)],
                    [round(lon + d, 6), round(lat + d, 6)],
                    [round(lon, 6), round(lat + d, 6)],
                    [round(lon, 6), round(lat, 6)],
                ]
            ]
        features.append(
            GeoFeature(
                feature_id=fid,
                geometry_type=geometry_type,
                coordinates=coords,
                properties={"region": region, "parcel_index": i},
            )
        )
    return features


# ----------------------------------------------------------------- main


_GRADE_LABEL = {"A": "Excellent", "B": "Good", "C": "Marginal", "D": "Poor"}

REGIONS = [
    ("Thames Valley", 5),
    ("Rhine Delta", 4),
    ("Sacramento Basin", 4),
]


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    for region, count in REGIONS:
        features = _synthetic_features(region, count)
        print(f"\n── {region} ({count} features) ──")
        print(f"  {'ID':<32} {'GR':<4} {'SCORE':<7} {'SIGNALS':<30} MISSING")
        print("  " + "─" * 85)

        for feat in features:
            result = await t.run(RunRequest(parameters={"feature": feat}))

            if "score" in result.outputs:
                s: SuitabilityScore = result.outputs["score"]
                signals_str = "+".join(s.signals_used)
                missing_str = ", ".join(s.signals_missing) if s.signals_missing else "—"
                label = _GRADE_LABEL[s.grade]
                print(
                    f"  {feat.feature_id:<32} {s.grade:<4} {s.score:<7.3f} "
                    f"{signals_str:<30} {missing_str}"
                )
                # Print factor summary on a second line, indented.
                factor_summary = " | ".join(f"{k}: {v}" for k, v in s.factors.items())
                print(f"    [{label}] {factor_summary}")
            else:
                exc = result.exceptions[0] if result.exceptions else None
                msg = exc.message[:60] if exc else "unknown error"
                print(f"  {feat.feature_id:<32} PIPELINE FAILED  {msg}")


if __name__ == "__main__":
    asyncio.run(main())
