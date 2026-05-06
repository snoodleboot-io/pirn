"""Unit tests for :class:`TissueSegmenter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.pathology.tissue_segmenter import TissueSegmenter
from pirn.domains.health.types.wsi_tile import WSITile

_CFG = KnotConfig(id="s")
_TILE = WSITile(slide_id="S", tile_x=0, tile_y=0, level=0, width=512, height=512)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TissueSegmenter:
        return TissueSegmenter(tiles=(_TILE,), threshold=0.5, _config=_CFG)

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "tiles"):
            await knot.process(tiles=42, threshold=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_tile(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "WSITile"):
            await knot.process(tiles=["x"], threshold=0.5)  # type: ignore[list-item]

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "numeric"):
            await knot.process(tiles=(_TILE,), threshold="x")  # type: ignore[arg-type]

    async def test_rejects_out_of_range_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            await knot.process(tiles=(_TILE,), threshold=1.5)

    async def test_returns_tile_tuple(self) -> None:
        knot = self._make_knot()
        out = await knot.process(tiles=(_TILE,), threshold=0.5)
        assert isinstance(out, tuple)
        assert all(isinstance(x, WSITile) for x in out)
