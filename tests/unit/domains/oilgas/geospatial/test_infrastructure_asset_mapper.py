"""Unit tests for :class:`InfrastructureAssetMapper`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.oilgas.geospatial.infrastructure_asset_mapper import (
    InfrastructureAssetMapper,
)
from pirn.tapestry import Tapestry

_ASSETS: list[dict[str, Any]] = [
    {"asset_id": "W-1", "asset_type": "well", "coordinates": [1.0, 2.0]},
    {"asset_id": "P-1", "asset_type": "pipeline", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
]


def _make_knot(coordinate_system: str = "EPSG:4326") -> InfrastructureAssetMapper:
    with Tapestry():
        assets = Parameter("assets", list, default=[], _config=KnotConfig(id="assets"))
        return InfrastructureAssetMapper(
            assets=assets,
            coordinate_system=coordinate_system,
            _config=KnotConfig(id="iam"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_coordinate_system(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "coordinate_system"):
            await knot.process(assets=_ASSETS, coordinate_system="")

    async def test_returns_feature_collection(self) -> None:
        knot = _make_knot()
        out = await knot.process(assets=_ASSETS, coordinate_system="EPSG:4326")
        assert out["type"] == "FeatureCollection"
        assert isinstance(out["features"], list)
        assert len(out["features"]) == 2

    async def test_filters_by_asset_type(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            assets=_ASSETS,
            coordinate_system="EPSG:4326",
            asset_types=("well",),
        )
        assert len(out["features"]) == 1
        assert out["features"][0]["properties"]["asset_id"] == "W-1"

    async def test_point_geometry_for_single_coordinate(self) -> None:
        knot = _make_knot()
        assets = [{"asset_id": "W-1", "asset_type": "well", "coordinates": [1.0, 2.0]}]
        out = await knot.process(assets=assets, coordinate_system="EPSG:4326")
        assert out["features"][0]["geometry"]["type"] == "Point"
