"""Unit tests for :class:`WSITileExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.pathology.wsi_tile_extractor import WSITileExtractor
from pirn.domains.health.types.wsi_tile import WSITile

_CFG = KnotConfig(id="w")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> WSITileExtractor:
        return WSITileExtractor(slide_id="slide-1", level=0, tile_size=256, grid_rows=2, grid_cols=3, _config=_CFG)

    async def test_rejects_empty_slide_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(slide_id="", level=0, tile_size=256, grid_rows=2, grid_cols=3)

    async def test_rejects_non_int(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "int"):
            await knot.process(slide_id="s", level="x", tile_size=256, grid_rows=2, grid_cols=3)  # type: ignore[arg-type]

    async def test_rejects_negative_level(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "level"):
            await knot.process(slide_id="s", level=-1, tile_size=256, grid_rows=2, grid_cols=3)

    async def test_rejects_non_positive_size(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(slide_id="s", level=0, tile_size=0, grid_rows=2, grid_cols=3)

    async def test_returns_grid_of_tiles(self) -> None:
        knot = self._make_knot()
        out = await knot.process(slide_id="slide-1", level=0, tile_size=256, grid_rows=2, grid_cols=3)
        assert isinstance(out, tuple)
        assert len(out) == 6
        assert all(isinstance(x, WSITile) for x in out)
