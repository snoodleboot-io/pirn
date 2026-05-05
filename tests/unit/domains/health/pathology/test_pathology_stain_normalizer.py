"""Unit tests for :class:`PathologyStainNormalizer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.pathology_stain_normalizer import PathologyStainNormalizer
from pirn.tapestry import Tapestry


@knot
async def emit_image_tile() -> dict[str, Any]:
    return {
        "pixel_data": [200, 150, 100],
        "width_px": 256,
        "height_px": 256,
    }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_image_tile(self) -> None:
        with self.assertRaisesRegex(TypeError, "image_tile"):
            PathologyStainNormalizer(
                image_tile="not-a-knot",  # type: ignore[arg-type]
                method="macenko",
                _config=KnotConfig(id="n"),
            )

    def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            t = emit_image_tile(_config=KnotConfig(id="t"))
            with self.assertRaisesRegex(ValueError, "method"):
                PathologyStainNormalizer(
                    image_tile=t,
                    method="unknown",
                    _config=KnotConfig(id="n"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            tile = emit_image_tile(_config=KnotConfig(id="tile"))
            PathologyStainNormalizer(
                image_tile=tile,
                method="macenko",
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["n"]
        assert isinstance(out, dict)
        assert "normalized_pixel_data" in out
        assert "stain_matrix" in out
        assert "method" in out
        assert out["method"] == "macenko"

    async def test_vahadane_method(self) -> None:
        with Tapestry() as t:
            tile = emit_image_tile(_config=KnotConfig(id="tile"))
            PathologyStainNormalizer(
                image_tile=tile,
                method="vahadane",
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["n"]
        assert out["method"] == "vahadane"
