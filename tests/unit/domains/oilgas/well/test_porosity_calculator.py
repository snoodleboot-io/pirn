"""Unit tests for :class:`PorosityCalculator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.porosity_calculator import PorosityCalculator
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_method(self) -> None:
        k = PorosityCalculator.__new__(PorosityCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "method"):
            await k.process(
                las_file=LASFile(well_id="W", curves=("GR",)),
                method="not_real",
                matrix_density=2.65,
                fluid_density=1.0,
            )

    async def test_rejects_non_positive_density(self) -> None:
        k = PorosityCalculator.__new__(PorosityCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "matrix_density"):
            await k.process(
                las_file=LASFile(well_id="W", curves=("GR",)),
                method="density",
                matrix_density=-2.65,
                fluid_density=1.0,
            )

    async def test_rejects_inverted_densities(self) -> None:
        k = PorosityCalculator.__new__(PorosityCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "fluid_density"):
            await k.process(
                las_file=LASFile(well_id="W", curves=("GR",)),
                method="density",
                matrix_density=1.0,
                fluid_density=2.65,
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_porosity_curve(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )
            PorosityCalculator(
                las_file=las,
                method="density",
                matrix_density=2.65,
                fluid_density=1.0,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, LASFile)
        assert "PHI_density" in out.curves
