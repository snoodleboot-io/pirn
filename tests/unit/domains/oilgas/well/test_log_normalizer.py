"""Unit tests for :class:`LogNormalizer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.log_normalizer import LogNormalizer
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_numeric_step(self) -> None:
        with pytest.raises(TypeError, match="target_depth_step"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                LogNormalizer(
                    las_file=las,
                    target_depth_step="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ln"),
                )

    def test_rejects_non_positive_step(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                LogNormalizer(
                    las_file=las,
                    target_depth_step=0.0,
                    _config=KnotConfig(id="ln"),
                )

    def test_rejects_invalid_unit(self) -> None:
        with pytest.raises(ValueError, match="target_depth_unit"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                LogNormalizer(
                    las_file=las,
                    target_depth_step=0.5,
                    target_depth_unit="cm",
                    _config=KnotConfig(id="ln"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_changes_depth_unit(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                depth_unit="m",
                _config=KnotConfig(id="i"),
            )
            LogNormalizer(
                las_file=las,
                target_depth_step=0.5,
                target_depth_unit="ft",
                _config=KnotConfig(id="ln"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ln"]
        assert isinstance(out, LASFile)
        assert out.depth_unit == "ft"
