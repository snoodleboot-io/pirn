"""Unit tests for :class:`WSITileExtractor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.wsi_tile_extractor import WSITileExtractor
from pirn.domains.health.types.wsi_tile import WSITile
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_slide_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            WSITileExtractor(
                slide_id="",
                level=0,
                tile_size=256,
                grid_rows=2,
                grid_cols=2,
                _config=KnotConfig(id="w"),
            )

    def test_rejects_non_int(self) -> None:
        with self.assertRaisesRegex(TypeError, "int"):
            WSITileExtractor(
                slide_id="s",
                level="x",  # type: ignore[arg-type]
                tile_size=256,
                grid_rows=2,
                grid_cols=2,
                _config=KnotConfig(id="w"),
            )

    def test_rejects_negative_level(self) -> None:
        with self.assertRaisesRegex(ValueError, "level"):
            WSITileExtractor(
                slide_id="s",
                level=-1,
                tile_size=256,
                grid_rows=2,
                grid_cols=2,
                _config=KnotConfig(id="w"),
            )

    def test_rejects_non_positive_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            WSITileExtractor(
                slide_id="s",
                level=0,
                tile_size=0,
                grid_rows=2,
                grid_cols=2,
                _config=KnotConfig(id="w"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_grid_of_tiles(self) -> None:
        with Tapestry() as t:
            WSITileExtractor(
                slide_id="slide-1",
                level=0,
                tile_size=256,
                grid_rows=2,
                grid_cols=3,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, tuple)
        assert len(out) == 6
        assert all(isinstance(x, WSITile) for x in out)
