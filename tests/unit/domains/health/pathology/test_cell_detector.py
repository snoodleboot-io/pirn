"""Unit tests for :class:`CellDetector`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.cell_detector import CellDetector
from pirn.domains.health.types.wsi_tile import WSITile
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "tiles"):
            CellDetector(
                tiles=42,  # type: ignore[arg-type]
                model_name="m",
                _config=KnotConfig(id="d"),
            )

    def test_rejects_non_tile(self) -> None:
        with self.assertRaisesRegex(TypeError, "WSITile"):
            CellDetector(
                tiles=["x"],  # type: ignore[list-item]
                model_name="m",
                _config=KnotConfig(id="d"),
            )

    def test_rejects_empty_model(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            CellDetector(
                tiles=(),
                model_name="",
                _config=KnotConfig(id="d"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_tile_count_mapping(self) -> None:
        tiles = (WSITile(slide_id="S", tile_x=0, tile_y=0, level=0, width=512, height=512),)
        with Tapestry() as t:
            CellDetector(
                tiles=tiles,
                model_name="stardist",
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, Mapping)
        assert (0, 0) in out
