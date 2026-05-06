"""Unit tests for :class:`LasFileIngester`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LasFileIngester:
        return LasFileIngester(
            file_path="/x",
            well_id="W",
            curves=("GR",),
            _config=KnotConfig(id="i"),
        )

    async def test_rejects_empty_file_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "file_path"):
            await knot.process(file_path="", well_id="W", curves=("GR",))

    async def test_rejects_empty_well_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "well_id"):
            await knot.process(file_path="/x", well_id="", curves=("GR",))

    async def test_rejects_empty_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "curves"):
            await knot.process(file_path="/x", well_id="W", curves=())

    async def test_rejects_invalid_depth_unit(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "depth_unit"):
            await knot.process(file_path="/x", well_id="W", curves=("GR",), depth_unit="km")

    async def test_returns_las_file(self) -> None:
        knot = self._make_knot()
        out = await knot.process(file_path="/x", well_id="W", curves=("GR", "RHOB"))
        assert isinstance(out, LASFile)
        assert out.well_id == "W"
        assert out.curves == ("GR", "RHOB")
