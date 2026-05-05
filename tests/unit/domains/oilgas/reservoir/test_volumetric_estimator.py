"""Unit tests for :class:`VolumetricEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.volumetric_estimator import VolumetricEstimator
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_area(self) -> None:
        with self.assertRaisesRegex(ValueError, "area_acres"):
            VolumetricEstimator(
                area_acres=0.0,
                net_thickness_ft=10.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                _config=KnotConfig(id="ve"),
            )

    def test_rejects_porosity_out_of_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "porosity_fraction"):
            VolumetricEstimator(
                area_acres=100.0,
                net_thickness_ft=10.0,
                porosity_fraction=1.5,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                _config=KnotConfig(id="ve"),
            )

    def test_rejects_non_numeric_sw(self) -> None:
        with self.assertRaisesRegex(TypeError, "water_saturation_fraction"):
            VolumetricEstimator(
                area_acres=100.0,
                net_thickness_ft=10.0,
                porosity_fraction=0.2,
                water_saturation_fraction="x",  # type: ignore[arg-type]
                formation_volume_factor=1.1,
                _config=KnotConfig(id="ve"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_positive_ooip(self) -> None:
        with Tapestry() as t:
            VolumetricEstimator(
                area_acres=100.0,
                net_thickness_ft=20.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                _config=KnotConfig(id="ve"),
            )
        result = await t.run(RunRequest())
        ooip = result.outputs["ve"]
        assert isinstance(ooip, float)
        assert ooip > 0.0
