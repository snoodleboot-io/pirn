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
    uv run python -m examples.domain_formats.geospatial_layer_analysis
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.domain_formats.geospatial_layer_analysis.core_assessment_knot import (
    CoreAssessmentKnot,
)
from examples.domain_formats.geospatial_layer_analysis.elevation_lookup import ElevationLookup
from examples.domain_formats.geospatial_layer_analysis.geo_feature import GeoFeature
from examples.domain_formats.geospatial_layer_analysis.land_cover_classifier import (
    LandCoverClassifier,
)
from examples.domain_formats.geospatial_layer_analysis.planning_zone_lookup import (
    PlanningZoneLookup,
)
from examples.domain_formats.geospatial_layer_analysis.suitability_score import SuitabilityScore
from examples.domain_formats.geospatial_layer_analysis.suitability_scorer import SuitabilityScorer


class GeospatialLayerAnalysis:
    """Builds and runs the layer-analysis tapestry over several synthetic regions."""

    _grade_label: ClassVar[dict[str, str]] = {
        "A": "Excellent",
        "B": "Good",
        "C": "Marginal",
        "D": "Poor",
    }
    _regions: ClassVar[tuple[tuple[str, int], ...]] = (
        ("Thames Valley", 5),
        ("Rhine Delta", 4),
        ("Sacramento Basin", 4),
    )

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire the required core assessment and three optional enrichments into a score."""
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

    @staticmethod
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

    @classmethod
    async def main(cls) -> None:
        """Score every synthetic feature in every region and print the graded table."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        for region, count in cls._regions:
            features = cls._synthetic_features(region, count)
            print(f"\n── {region} ({count} features) ──")
            print(f"  {'ID':<32} {'GR':<4} {'SCORE':<7} {'SIGNALS':<30} MISSING")
            print("  " + "─" * 85)

            for feat in features:
                result = await t.run(RunRequest(parameters={"feature": feat}))

                if "score" in result.outputs:
                    s: SuitabilityScore = result.outputs["score"]
                    signals_str = "+".join(s.signals_used)
                    missing_str = ", ".join(s.signals_missing) if s.signals_missing else "—"
                    label = cls._grade_label[s.grade]
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
