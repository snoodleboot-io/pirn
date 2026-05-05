"""Unit tests for :class:`WellLocationProjector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.geospatial.well_location_projector import (
    WellLocationProjector,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_well_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "well_id"):
            WellLocationProjector(
                well_id="",
                longitude_deg=0.0,
                latitude_deg=0.0,
                target_crs="EPSG:32613",
                _config=KnotConfig(id="wp"),
            )

    def test_rejects_out_of_range_longitude(self) -> None:
        with self.assertRaisesRegex(ValueError, r"longitude"):
            WellLocationProjector(
                well_id="W",
                longitude_deg=360.0,
                latitude_deg=0.0,
                target_crs="EPSG:32613",
                _config=KnotConfig(id="wp"),
            )

    def test_rejects_out_of_range_latitude(self) -> None:
        with self.assertRaisesRegex(ValueError, r"latitude"):
            WellLocationProjector(
                well_id="W",
                longitude_deg=0.0,
                latitude_deg=180.0,
                target_crs="EPSG:32613",
                _config=KnotConfig(id="wp"),
            )

    def test_rejects_empty_target_crs(self) -> None:
        with self.assertRaisesRegex(ValueError, "target_crs"):
            WellLocationProjector(
                well_id="W",
                longitude_deg=0.0,
                latitude_deg=0.0,
                target_crs="",
                _config=KnotConfig(id="wp"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_projected_location(self) -> None:
        with Tapestry() as t:
            WellLocationProjector(
                well_id="W",
                longitude_deg=-105.0,
                latitude_deg=40.0,
                target_crs="EPSG:32613",
                _config=KnotConfig(id="wp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["wp"]
        assert out["well_id"] == "W"
        assert out["crs"] == "EPSG:32613"
