"""``InfrastructureAssetMapper`` — map infrastructure assets to a GeoJSON FeatureCollection."""

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
        coordinate_system: str,
        asset_types: tuple[str, ...] = ("well", "pipeline", "facility"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(coordinate_system, str) or not coordinate_system:
            raise ValueError(
                "InfrastructureAssetMapper: coordinate_system must be a non-empty string"
            )
        self._coordinate_system = coordinate_system
        self._asset_types = asset_types
        super().__init__(assets=assets, _config=_config, **kwargs)

    async def process(
        self, assets: list[dict[str, Any]], **_: Any
    ) -> dict[str, Any]:
        """Map infrastructure assets to a GeoJSON FeatureCollection.

        Args:
            assets: List of asset dicts with ``asset_id``, ``asset_type``, and
                ``coordinates`` (list of [x, y] or single [x, y]).

        Returns:
            GeoJSON FeatureCollection dict with ``type`` and ``features``.
        """
        features: list[dict[str, Any]] = []
        for asset in assets:
            if asset.get("asset_type") not in self._asset_types:
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
                        "coordinate_system": self._coordinate_system,
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}
