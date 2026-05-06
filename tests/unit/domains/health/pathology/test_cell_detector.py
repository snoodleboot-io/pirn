"""Unit tests for :class:`CellDetector`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.pathology.cell_detector import CellDetector
from pirn.domains.health.types.wsi_tile import WSITile

_CFG = KnotConfig(id="d")
_TILE = WSITile(slide_id="S", tile_x=0, tile_y=0, level=0, width=512, height=512)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> CellDetector:
        return CellDetector(tiles=(_TILE,), model_name="stardist", _config=_CFG)

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "tiles"):
            await knot.process(tiles=42, model_name="stardist")  # type: ignore[arg-type]

    async def test_rejects_non_tile(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "WSITile"):
            await knot.process(tiles=["x"], model_name="stardist")  # type: ignore[list-item]

    async def test_rejects_empty_model(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(tiles=(_TILE,), model_name="")

    async def test_returns_per_tile_count_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(tiles=(_TILE,), model_name="stardist")
        assert isinstance(out, Mapping)
        assert (0, 0) in out
