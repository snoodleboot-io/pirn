"""Unit tests for :class:`WaterSaturationCalculator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.water_saturation_calculator import (
    WaterSaturationCalculator,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                WaterSaturationCalculator(
                    las_file=las,
                    method="bogus",
                    rw=0.05,
                    _config=KnotConfig(id="sw"),
                )

    def test_rejects_non_positive_rw(self) -> None:
        with self.assertRaisesRegex(ValueError, "rw"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                WaterSaturationCalculator(
                    las_file=las,
                    method="archie",
                    rw=0.0,
                    _config=KnotConfig(id="sw"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_sw_curve(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )
            WaterSaturationCalculator(
                las_file=las,
                method="archie",
                rw=0.05,
                _config=KnotConfig(id="sw"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sw"]
        assert isinstance(out, LASFile)
        assert "SW_archie" in out.curves
