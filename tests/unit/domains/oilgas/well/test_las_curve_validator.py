"""Unit tests for :class:`LasCurveValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_curve_validator import LasCurveValidator

_LAS = LASFile(well_id="W", curves=("GR", "RHOB"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LasCurveValidator:
        return LasCurveValidator(
            las_file=None,  # type: ignore[arg-type]
            required_curves=("GR",),
            _config=KnotConfig(id="v", validate_io=False),
        )

    async def test_rejects_empty_required_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "required_curves"):
            await knot.process(las_file=_LAS, required_curves=())

    async def test_passes_when_all_present(self) -> None:
        knot = self._make_knot()
        out = await knot.process(las_file=_LAS, required_curves=("GR",))
        assert isinstance(out, LASFile)

    async def test_fails_when_missing(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(las_file=_LAS, required_curves=("MISSING",))
