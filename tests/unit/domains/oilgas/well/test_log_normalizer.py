"""Unit tests for :class:`LogNormalizer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.log_normalizer import LogNormalizer

_LAS = LASFile(well_id="W", curves=("GR",), depth_unit="m")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LogNormalizer:
        return LogNormalizer(
            las_file=None,  # type: ignore[arg-type]
            target_depth_step=0.5,
            _config=KnotConfig(id="ln", validate_io=False),
        )

    async def test_rejects_non_numeric_step(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "target_depth_step"):
            await knot.process(las_file=_LAS, target_depth_step="x")  # type: ignore[arg-type]

    async def test_rejects_non_positive_step(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(las_file=_LAS, target_depth_step=0.0)

    async def test_rejects_invalid_unit(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "target_depth_unit"):
            await knot.process(las_file=_LAS, target_depth_step=0.5, target_depth_unit="cm")

    async def test_changes_depth_unit(self) -> None:
        knot = self._make_knot()
        out = await knot.process(las_file=_LAS, target_depth_step=0.5, target_depth_unit="ft")
        assert isinstance(out, LASFile)
        assert out.depth_unit == "ft"
