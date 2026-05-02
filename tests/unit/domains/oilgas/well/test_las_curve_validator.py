"""Unit tests for :class:`LasCurveValidator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_curve_validator import LasCurveValidator
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_required_curves(self) -> None:
        with pytest.raises(ValueError, match="required_curves"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                LasCurveValidator(
                    las_file=las,
                    required_curves=(),
                    _config=KnotConfig(id="v"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_passes_when_all_present(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR", "RHOB"),
                _config=KnotConfig(id="i"),
            )
            LasCurveValidator(
                las_file=las,
                required_curves=("GR",),
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["v"]
        assert isinstance(out, LASFile)

    async def test_fails_when_missing(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )
            LasCurveValidator(
                las_file=las,
                required_curves=("MISSING",),
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
