"""Unit tests for :class:`PathologyStainNormalizer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_health.pathology.pathology_stain_normalizer import PathologyStainNormalizer

_CFG = KnotConfig(id="n")
_IMAGE_TILE: dict[str, Any] = {
    "pixel_data": [200, 150, 100],
    "width_px": 256,
    "height_px": 256,
}


def _make_knot() -> PathologyStainNormalizer:
    with Tapestry():
        src = Parameter("tile", dict, default=_IMAGE_TILE, _config=KnotConfig(id="tile"))
        return PathologyStainNormalizer(image_tile=src, method="macenko", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_image_tile(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "dict"):
            await knot.process(image_tile="not-a-dict", method="macenko")  # type: ignore[arg-type]

    async def test_rejects_invalid_method(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(image_tile=_IMAGE_TILE, method="unknown")

    async def test_returns_dict_with_required_keys(self) -> None:
        knot = _make_knot()
        out = await knot.process(image_tile=_IMAGE_TILE, method="macenko")
        assert isinstance(out, dict)
        assert "normalized_pixel_data" in out
        assert "stain_matrix" in out
        assert "method" in out
        assert out["method"] == "macenko"

    async def test_vahadane_method(self) -> None:
        knot = _make_knot()
        out = await knot.process(image_tile=_IMAGE_TILE, method="vahadane")
        assert out["method"] == "vahadane"
