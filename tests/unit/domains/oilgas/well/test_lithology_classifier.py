"""Unit tests for :class:`LithologyClassifier`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.lithology_classifier import LithologyClassifier

_LAS = LASFile(well_id="W", curves=("GR",))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LithologyClassifier:
        return LithologyClassifier(
            las_file=None,  # type: ignore[arg-type]
            method="rule_based",
            _config=KnotConfig(id="lc", validate_io=False),
        )

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(las_file=_LAS, method="nope")

    async def test_appends_lith_curve(self) -> None:
        knot = self._make_knot()
        out = await knot.process(las_file=_LAS, method="rule_based")
        assert isinstance(out, LASFile)
        assert "LITH" in out.curves
