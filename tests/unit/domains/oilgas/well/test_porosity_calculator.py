"""Unit tests for :class:`PorosityCalculator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.porosity_calculator import PorosityCalculator
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="method"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                PorosityCalculator(
                    las_file=las,
                    method="not_real",
                    matrix_density=2.65,
                    fluid_density=1.0,
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_non_positive_density(self) -> None:
        with pytest.raises(ValueError, match="matrix_density"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                PorosityCalculator(
                    las_file=las,
                    method="density",
                    matrix_density=-2.65,
                    fluid_density=1.0,
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_inverted_densities(self) -> None:
        with pytest.raises(ValueError, match="fluid_density"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                PorosityCalculator(
                    las_file=las,
                    method="density",
                    matrix_density=1.0,
                    fluid_density=2.65,
                    _config=KnotConfig(id="p"),
                )


@pytest.mark.asyncio
class TestProcess:
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
