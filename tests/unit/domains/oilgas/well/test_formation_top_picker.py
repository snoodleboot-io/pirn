"""Unit tests for :class:`FormationTopPicker`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.types.formation_top import FormationTop
from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.well.formation_top_picker import FormationTopPicker

_LAS = LASFile(well_id="W", curves=("GR",))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FormationTopPicker:
        return FormationTopPicker(
            las_file=None,  # type: ignore[arg-type]
            formation_name="Niobrara",
            depth_md=2500.0,
            _config=KnotConfig(id="ft", validate_io=False),
        )

    async def test_rejects_empty_formation_name(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "formation_name"):
            await knot.process(las_file=_LAS, formation_name="", depth_md=100.0)

    async def test_rejects_negative_depth(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "depth_md"):
            await knot.process(las_file=_LAS, formation_name="N", depth_md=-1.0)

    async def test_rejects_non_numeric_depth(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "depth_md"):
            await knot.process(las_file=_LAS, formation_name="N", depth_md="x")  # type: ignore[arg-type]

    async def test_returns_formation_top(self) -> None:
        knot = self._make_knot()
        out = await knot.process(las_file=_LAS, formation_name="Niobrara", depth_md=2500.0)
        assert isinstance(out, FormationTop)
        assert out.formation_name == "Niobrara"
        assert out.depth_md == 2500.0
