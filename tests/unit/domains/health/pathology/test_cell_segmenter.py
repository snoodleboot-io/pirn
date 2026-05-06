"""Unit tests for :class:`CellSegmenter`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.pathology.cell_segmenter import CellSegmenter
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="cs")
_TILE_DATA: dict[str, Any] = {
    "pixel_data": [255, 128, 0],
    "width_px": 512,
    "height_px": 512,
    "resolution_um_per_px": 0.25,
}


def _make_knot() -> CellSegmenter:
    with Tapestry():
        src = Parameter("tile", dict, default=_TILE_DATA, _config=KnotConfig(id="tile"))
        return CellSegmenter(
            image_tile=src,
            min_cell_diameter_um=5.0,
            max_cell_diameter_um=30.0,
            stain_type="hematoxylin",
            _config=_CFG,
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_image_tile(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "dict"):
            await knot.process(image_tile="not-a-dict", min_cell_diameter_um=5.0, max_cell_diameter_um=30.0, stain_type="hematoxylin")  # type: ignore[arg-type]

    async def test_rejects_non_positive_min_diameter(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "min_cell_diameter_um"):
            await knot.process(image_tile=_TILE_DATA, min_cell_diameter_um=0.0, max_cell_diameter_um=30.0, stain_type="hematoxylin")

    async def test_rejects_max_le_min(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "max_cell_diameter_um"):
            await knot.process(image_tile=_TILE_DATA, min_cell_diameter_um=20.0, max_cell_diameter_um=10.0, stain_type="hematoxylin")

    async def test_rejects_invalid_stain_type(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "stain_type"):
            await knot.process(image_tile=_TILE_DATA, min_cell_diameter_um=5.0, max_cell_diameter_um=30.0, stain_type="unknown")

    async def test_returns_dict_with_required_keys(self) -> None:
        knot = _make_knot()
        out = await knot.process(image_tile=_TILE_DATA, min_cell_diameter_um=5.0, max_cell_diameter_um=30.0, stain_type="hematoxylin")
        assert isinstance(out, dict)
        assert "cell_count" in out
        assert "cell_masks" in out
        assert "mean_cell_area_um2" in out
        assert isinstance(out["cell_count"], int)
        assert isinstance(out["cell_masks"], list)
