Performs oilgas geospatial analysis — coordinate transformation, lease block grouping, well location projection, and fault and boundary proximity checks. Does NOT read GeoTIFF or Shapefile; use GeoTiffFormat/ShapefileFormat from file_formats.

## Mental model

Oilgas geospatial knots operate on already-loaded geometry objects — points, polygons, and line features ingested upstream by file-format or database source knots. The core flow is: transform all geometries to a common CRS, group or project locations against reference features (lease blocks, fields, faults), then compute proximity metrics for regulatory or engineering decisions. All knots are stateless and side-effect-free; they do not write spatial databases.

## Source map

```
├── boundary_proximity_checker.py       BoundaryProximityChecker       — computes distance from well locations to regulatory or lease boundaries
├── coordinate_system_transformer.py    CoordinateSystemTransformer    — reprojects geometries between named CRS (EPSG codes or WKT)
├── fault_proximity_analyzer.py         FaultProximityAnalyzer         — measures proximity of well paths or targets to mapped fault traces
├── field_boundary_definer.py           FieldBoundaryDefiner           — constructs field boundary polygons from well cluster or lease geometry
├── infrastructure_asset_mapper.py      InfrastructureAssetMapper      — maps pipeline, facility, and wellhead assets to a unified spatial layer
├── lease_block_grouper.py              LeaseBlockGrouper              — assigns wells and assets to lease blocks using spatial join
├── well_location_projector.py          WellLocationProjector          — projects surface and bottomhole well locations onto a reference grid
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_oilgas.geospatial import (
    CoordinateSystemTransformer,
    LeaseBlockGrouper,
    BoundaryProximityChecker,
)

with Tapestry() as t:
    well_locations = Parameter("well_locations", object)   # GeoDataFrame from ShapefileFormat
    lease_blocks   = Parameter("lease_blocks", object)     # GeoDataFrame from ShapefileFormat

    transformed = CoordinateSystemTransformer(
        geometries=well_locations,
        _config=KnotConfig(id="crs_transform", params={"target_epsg": 32638}),
    )

    grouped = LeaseBlockGrouper(
        wells=transformed,
        blocks=lease_blocks,
        _config=KnotConfig(id="lease_group"),
    )

    proximity = BoundaryProximityChecker(
        locations=grouped,
        boundaries=lease_blocks,
        _config=KnotConfig(id="boundary_prox", params={"threshold_m": 500}),
    )

result = await t.run(RunRequest(parameters={"well_locations": well_gdf, "lease_blocks": block_gdf}))
```

## Anti-patterns

**Passing mixed-CRS geometries to LeaseBlockGrouper without CoordinateSystemTransformer** — spatial joins across mismatched projections produce silently incorrect block assignments; always transform to a single CRS first.

**Using FieldBoundaryDefiner on sparse well clusters** — convex hull boundaries derived from fewer than four well locations are unreliable; supplement with lease polygon inputs via `LeaseBlockGrouper` where coverage is sparse.

**Running FaultProximityAnalyzer with unprojected geographic coordinates** — distance calculations in degrees produce meaningless results at high latitudes; always reproject to a metric CRS before proximity analysis.

## Constraints and gotchas

- `CoordinateSystemTransformer` accepts EPSG integer codes or WKT strings; invalid codes raise `CrsLookupError` at knot initialisation.
- `LeaseBlockGrouper` performs a spatial join; the `wells` and `blocks` inputs must share the same CRS or the knot raises `CrsMismatchError`.
- `BoundaryProximityChecker` emits a `ProximityFlag` record for each location within `threshold_m`; it does not filter records — downstream knots must apply any blocking logic.
- `WellLocationProjector` requires both surface and bottomhole coordinates; passing surface-only data returns projected surface points with a warning, not an error.
- Install extra: `pip install pirn[geospatial]`

## Quick reference

| Task | How |
|------|-----|
| Reproject geometries to a target CRS | `CoordinateSystemTransformer(geometries=param, target_epsg=32638)` |
| Assign wells to lease blocks | `LeaseBlockGrouper(wells=transformed, blocks=blocks)` |
| Check proximity to regulatory boundary | `BoundaryProximityChecker(locations=grouped, boundaries=boundaries)` |
| Project well paths onto reference grid | `WellLocationProjector(wells=transformed, grid=grid)` |
| Measure distance to fault traces | `FaultProximityAnalyzer(wells=transformed, faults=fault_geom)` |
| Define field boundary from geometry | `FieldBoundaryDefiner(wells=grouped)` |
| Unify asset spatial layers | `InfrastructureAssetMapper(assets=asset_list)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
