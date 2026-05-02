"""Unit tests for :class:`CoordinateSystemTransformer`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.geospatial.coordinate_system_transformer import (
    CoordinateSystemTransformer,
)
from pirn.tapestry import Tapestry


class _LocationSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"well_id": "W", "x": 100.0, "y": 200.0, "crs": "EPSG:4326"}


class TestConstruction:
    def test_rejects_empty_target_crs(self) -> None:
        with pytest.raises(ValueError, match="target_crs"):
            with Tapestry():
                src = _LocationSource(_config=KnotConfig(id="src"))
                CoordinateSystemTransformer(
                    location=src,
                    target_crs="",
                    _config=KnotConfig(id="cst"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_transformed_dict(self) -> None:
        with Tapestry() as t:
            src = _LocationSource(_config=KnotConfig(id="src"))
            CoordinateSystemTransformer(
                location=src,
                target_crs="EPSG:32613",
                _config=KnotConfig(id="cst"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cst"]
        assert out["well_id"] == "W"
        assert out["crs"] == "EPSG:32613"
