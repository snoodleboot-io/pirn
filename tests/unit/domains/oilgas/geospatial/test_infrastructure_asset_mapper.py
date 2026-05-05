"""Unit tests for :class:`InfrastructureAssetMapper`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.geospatial.infrastructure_asset_mapper import (
    InfrastructureAssetMapper,
)
from pirn.tapestry import Tapestry


class _AssetsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"asset_id": "W-1", "asset_type": "well", "coordinates": [1.0, 2.0]},
            {"asset_id": "P-1", "asset_type": "pipeline", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
        ]


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_coordinate_system(self) -> None:
        with self.assertRaisesRegex(ValueError, "coordinate_system"):
            with Tapestry():
                src = _AssetsSource(_config=KnotConfig(id="src"))
                InfrastructureAssetMapper(
                    assets=src,
                    coordinate_system="",
                    _config=KnotConfig(id="iam"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_feature_collection(self) -> None:
        with Tapestry() as t:
            src = _AssetsSource(_config=KnotConfig(id="src"))
            InfrastructureAssetMapper(
                assets=src,
                coordinate_system="EPSG:4326",
                _config=KnotConfig(id="iam"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["iam"]
        assert out["type"] == "FeatureCollection"
        assert isinstance(out["features"], list)
        assert len(out["features"]) == 2
