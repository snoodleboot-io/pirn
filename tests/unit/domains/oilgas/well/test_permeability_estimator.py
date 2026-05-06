"""Unit tests for :class:`PermeabilityEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.permeability_estimator import PermeabilityEstimator
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_method(self) -> None:
        k = PermeabilityEstimator.__new__(PermeabilityEstimator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "method"):
            await k.process(
                las_file=LASFile(well_id="W", curves=("GR",)),
                method="bogus",
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_permeability_curve(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )
            PermeabilityEstimator(
                las_file=las,
                method="timur",
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, LASFile)
        assert "K_timur" in out.curves
