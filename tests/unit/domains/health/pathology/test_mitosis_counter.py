"""Unit tests for :class:`MitosisCounter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.pathology.mitosis_counter import MitosisCounter
from pirn.domains.health.types.wsi_tile import WSITile

_CFG = KnotConfig(id="m")
_TILE = WSITile(slide_id="S", tile_x=0, tile_y=0, level=0, width=512, height=512)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> MitosisCounter:
        return MitosisCounter(tiles=(_TILE,), confidence_threshold=0.5, _config=_CFG)

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "tiles"):
            await knot.process(tiles=42, confidence_threshold=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_tile(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "WSITile"):
            await knot.process(tiles=["x"], confidence_threshold=0.5)  # type: ignore[list-item]

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "numeric"):
            await knot.process(tiles=(_TILE,), confidence_threshold="x")  # type: ignore[arg-type]

    async def test_rejects_out_of_range_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            await knot.process(tiles=(_TILE,), confidence_threshold=1.5)

    async def test_returns_int(self) -> None:
        knot = self._make_knot()
        out = await knot.process(tiles=(_TILE,), confidence_threshold=0.5)
        assert isinstance(out, int)
