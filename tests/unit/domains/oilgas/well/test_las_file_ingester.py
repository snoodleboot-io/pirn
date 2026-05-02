"""Unit tests for :class:`LasFileIngester`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_file_path(self) -> None:
        with pytest.raises(ValueError, match="file_path"):
            LasFileIngester(
                file_path="",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )

    def test_rejects_empty_well_id(self) -> None:
        with pytest.raises(ValueError, match="well_id"):
            LasFileIngester(
                file_path="/x",
                well_id="",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )

    def test_rejects_empty_curves(self) -> None:
        with pytest.raises(ValueError, match="curves"):
            LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=(),
                _config=KnotConfig(id="i"),
            )

    def test_rejects_invalid_depth_unit(self) -> None:
        with pytest.raises(ValueError, match="depth_unit"):
            LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                depth_unit="km",
                _config=KnotConfig(id="i"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_las_file(self) -> None:
        with Tapestry() as t:
            LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR", "RHOB"),
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, LASFile)
        assert out.well_id == "W"
        assert out.curves == ("GR", "RHOB")
