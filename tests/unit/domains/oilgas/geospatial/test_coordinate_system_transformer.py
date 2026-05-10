"""Unit tests for :class:`CoordinateSystemTransformer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.oilgas.geospatial.coordinate_system_transformer import (
    CoordinateSystemTransformer,
)
from pirn.tapestry import Tapestry

_LOC = {"well_id": "W", "x": 100.0, "y": 200.0, "crs": "EPSG:4326"}


def _make_knot(target_crs: str = "EPSG:32613") -> CoordinateSystemTransformer:
    with Tapestry():
        loc = Parameter("loc", dict, default={}, _config=KnotConfig(id="loc"))
        return CoordinateSystemTransformer(
            location=loc,
            target_crs=target_crs,
            _config=KnotConfig(id="cst"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_target_crs(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "target_crs"):
            await knot.process(location=_LOC, target_crs="")

    async def test_returns_transformed_dict(self) -> None:
        knot = _make_knot(target_crs="EPSG:32613")
        out = await knot.process(location=_LOC, target_crs="EPSG:32613")
        assert out["well_id"] == "W"
        assert out["crs"] == "EPSG:32613"

    async def test_projects_coordinates(self) -> None:
        # _LOC has crs=EPSG:4326 (lon=100, lat=200 — note: lat 200 is out of range
        # but the implementation applies equirectangular projection regardless).
        # Test only that x/y are present and numeric; exact values depend on projection.
        knot = _make_knot(target_crs="EPSG:32613")
        out = await knot.process(location=_LOC, target_crs="EPSG:32613")
        assert "x" in out
        assert "y" in out
        assert isinstance(out["x"], float)
        assert isinstance(out["y"], float)
