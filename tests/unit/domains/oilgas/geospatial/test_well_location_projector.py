"""Unit tests for :class:`WellLocationProjector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.geospatial.well_location_projector import (
    WellLocationProjector,
)
from pirn.tapestry import Tapestry


def _make_knot() -> WellLocationProjector:
    with Tapestry():
        return WellLocationProjector(
            well_id="W",
            longitude_deg=-105.0,
            latitude_deg=40.0,
            target_crs="EPSG:32613",
            _config=KnotConfig(id="wp"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_well_id(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "well_id"):
            await knot.process(well_id="", longitude_deg=0.0, latitude_deg=0.0, target_crs="EPSG:32613")

    async def test_rejects_out_of_range_longitude(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "longitude"):
            await knot.process(well_id="W", longitude_deg=360.0, latitude_deg=0.0, target_crs="EPSG:32613")

    async def test_rejects_out_of_range_latitude(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "latitude"):
            await knot.process(well_id="W", longitude_deg=0.0, latitude_deg=180.0, target_crs="EPSG:32613")

    async def test_rejects_empty_target_crs(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "target_crs"):
            await knot.process(well_id="W", longitude_deg=0.0, latitude_deg=0.0, target_crs="")

    async def test_returns_projected_location(self) -> None:
        knot = _make_knot()
        out = await knot.process(well_id="W", longitude_deg=-105.0, latitude_deg=40.0, target_crs="EPSG:32613")
        assert out["well_id"] == "W"
        assert out["crs"] == "EPSG:32613"
