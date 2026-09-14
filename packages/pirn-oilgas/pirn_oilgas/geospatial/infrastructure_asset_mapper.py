"""``InfrastructureAssetMapper`` — map infrastructure assets to a GeoJSON FeatureCollection.

Algorithm:
    1. Receive a list of asset dicts and a ``coordinate_system`` identifier.
    2. Validate that ``coordinate_system`` is non-empty.
    3. Filter assets whose ``asset_type`` is in ``asset_types``.
    4. Determine geometry type: ``Point`` for single (x, y), ``LineString``
       for a sequence of coordinates.
    5. Build a GeoJSON FeatureCollection and return it.


References:
    - OGC 08-791r6, GeoJSON (IETF RFC 7946) — geometry encoding for Points and
      LineStrings.
    - API RP 1173 — Pipeline Safety Management Systems, Appendix B (asset
      inventory and geospatial conventions).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class InfrastructureAssetMapper(Knot):
    """Map infrastructure assets to a GIS-ready GeoJSON FeatureCollection."""

    def __init__(
        self,
        *,
        assets: Knot,
        coordinate_system: Knot | str,
        asset_types: Knot | tuple[str, ...] = ("well", "pipeline", "facility"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            assets=assets,
            coordinate_system=coordinate_system,
            asset_types=asset_types,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        assets: list[dict[str, Any]],
        coordinate_system: str,
        asset_types: tuple[str, ...] = ("well", "pipeline", "facility"),
        **_: Any,
    ) -> dict[str, Any]:
        """Map infrastructure assets to a GeoJSON FeatureCollection.

        Args:
            assets: List of asset dicts with ``asset_id``, ``asset_type``, and
                ``coordinates`` (list of [x, y] or single [x, y]).
            coordinate_system: Non-empty CRS identifier string.
            asset_types: Tuple of asset type strings to include.

        Returns:
            GeoJSON FeatureCollection dict with ``type`` and ``features``.
        """
        if not isinstance(coordinate_system, str) or not coordinate_system:
            raise ValueError(
                "InfrastructureAssetMapper: coordinate_system must be a non-empty string"
            )
        features: list[dict[str, Any]] = []
        for asset in assets:
            if asset.get("asset_type") not in asset_types:
                continue
            coords = asset.get("coordinates", [])
            if coords and isinstance(coords[0], (int, float)):
                geometry: dict[str, Any] = {"type": "Point", "coordinates": coords}
            else:
                geometry = {"type": "LineString", "coordinates": coords}
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "asset_id": asset.get("asset_id"),
                        "asset_type": asset.get("asset_type"),
                        "coordinate_system": coordinate_system,
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}
