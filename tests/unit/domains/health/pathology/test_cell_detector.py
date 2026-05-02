"""Unit tests for :class:`CellDetector`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.cell_detector import CellDetector
from pirn.domains.health.types.wsi_tile import WSITile
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="tiles"):
            CellDetector(
                tiles=42,  # type: ignore[arg-type]
                model_name="m",
                _config=KnotConfig(id="d"),
            )

    def test_rejects_non_tile(self) -> None:
        with pytest.raises(TypeError, match="WSITile"):
            CellDetector(
                tiles=["x"],  # type: ignore[list-item]
                model_name="m",
                _config=KnotConfig(id="d"),
            )

    def test_rejects_empty_model(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            CellDetector(
                tiles=(),
                model_name="",
                _config=KnotConfig(id="d"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_per_tile_count_mapping(self) -> None:
        tiles = (WSITile(slide_id="S", tile_x=0, tile_y=0, level=0, width=512, height=512),)
        with Tapestry() as t:
            CellDetector(
                tiles=tiles,
                model_name="stardist",
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, Mapping)
        assert (0, 0) in out
