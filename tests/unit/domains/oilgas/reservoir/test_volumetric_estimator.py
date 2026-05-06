"""Unit tests for :class:`VolumetricEstimator`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.volumetric_estimator import VolumetricEstimator


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> VolumetricEstimator:
        return VolumetricEstimator(
            area_acres=100.0,
            net_thickness_ft=10.0,
            porosity_fraction=0.2,
            water_saturation_fraction=0.3,
            formation_volume_factor=1.1,
            _config=KnotConfig(id="ve"),
        )

    async def test_rejects_non_positive_area(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "area_acres"):
            await knot.process(
                area_acres=0.0,
                net_thickness_ft=10.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
            )

    async def test_rejects_porosity_out_of_range(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "porosity_fraction"):
            await knot.process(
                area_acres=100.0,
                net_thickness_ft=10.0,
                porosity_fraction=1.5,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
            )

    async def test_rejects_non_numeric_sw(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "water_saturation_fraction"):
            await knot.process(
                area_acres=100.0,
                net_thickness_ft=10.0,
                porosity_fraction=0.2,
                water_saturation_fraction="x",  # type: ignore[arg-type]
                formation_volume_factor=1.1,
            )

    async def test_returns_positive_ooip(self) -> None:
        knot = self._make_knot()
        ooip = await knot.process(
            area_acres=100.0,
            net_thickness_ft=20.0,
            porosity_fraction=0.2,
            water_saturation_fraction=0.3,
            formation_volume_factor=1.1,
        )
        assert isinstance(ooip, float)
        assert ooip > 0.0
