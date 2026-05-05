"""Unit tests for :class:`CellSegmenter`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.cell_segmenter import CellSegmenter
from pirn.tapestry import Tapestry


@knot
async def emit_image_tile() -> dict[str, Any]:
    return {
        "pixel_data": [255, 128, 0],
        "width_px": 512,
        "height_px": 512,
        "resolution_um_per_px": 0.25,
    }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_image_tile(self) -> None:
        with self.assertRaisesRegex(TypeError, "image_tile"):
            CellSegmenter(
                image_tile="not-a-knot",  # type: ignore[arg-type]
                min_cell_diameter_um=5.0,
                max_cell_diameter_um=30.0,
                stain_type="hematoxylin",
                _config=KnotConfig(id="cs"),
            )

    def test_rejects_non_positive_min_diameter(self) -> None:
        with Tapestry():
            t = emit_image_tile(_config=KnotConfig(id="t"))
            with self.assertRaisesRegex(ValueError, "min_cell_diameter_um"):
                CellSegmenter(
                    image_tile=t,
                    min_cell_diameter_um=0.0,
                    max_cell_diameter_um=30.0,
                    stain_type="hematoxylin",
                    _config=KnotConfig(id="cs"),
                )

    def test_rejects_invalid_stain_type(self) -> None:
        with Tapestry():
            t = emit_image_tile(_config=KnotConfig(id="t"))
            with self.assertRaisesRegex(ValueError, "stain_type"):
                CellSegmenter(
                    image_tile=t,
                    min_cell_diameter_um=5.0,
                    max_cell_diameter_um=30.0,
                    stain_type="unknown",
                    _config=KnotConfig(id="cs"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            tile = emit_image_tile(_config=KnotConfig(id="tile"))
            CellSegmenter(
                image_tile=tile,
                min_cell_diameter_um=5.0,
                max_cell_diameter_um=30.0,
                stain_type="hematoxylin",
                _config=KnotConfig(id="cs"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cs"]
        assert isinstance(out, dict)
        assert "cell_count" in out
        assert "cell_masks" in out
        assert "mean_cell_area_um2" in out
        assert isinstance(out["cell_count"], int)
        assert isinstance(out["cell_masks"], list)
