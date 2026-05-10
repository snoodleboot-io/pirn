"""Unit tests for :class:`LasCurveValidator`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload
from pirn.domains.oilgas.well.las_curve_validator import LasCurveValidator

_LAS = LASPayload(
    metadata=LASFile(well_id="W", curves=("GR", "RHOB")),
    data={"GR": np.zeros(10), "RHOB": np.zeros(10)},
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LasCurveValidator:
        return LasCurveValidator(
            payload=None,  # type: ignore[arg-type]
            required_curves=("GR",),
            _config=KnotConfig(id="v", validate_io=False),
        )

    async def test_rejects_empty_required_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "required_curves"):
            await knot.process(payload=_LAS, required_curves=())

    async def test_passes_when_all_present(self) -> None:
        knot = self._make_knot()
        out = await knot.process(payload=_LAS, required_curves=("GR",))
        assert isinstance(out, LASPayload)

    async def test_fails_when_missing(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(payload=_LAS, required_curves=("MISSING",))
