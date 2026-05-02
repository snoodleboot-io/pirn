"""Unit tests for :class:`TissueSegmenter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.tissue_segmenter import TissueSegmenter
from pirn.domains.health.types.wsi_tile import WSITile
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="tiles"):
            TissueSegmenter(
                tiles=42,  # type: ignore[arg-type]
                threshold=0.5,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_tile(self) -> None:
        with pytest.raises(TypeError, match="WSITile"):
            TissueSegmenter(
                tiles=["x"],  # type: ignore[list-item]
                threshold=0.5,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_numeric_threshold(self) -> None:
        with pytest.raises(TypeError, match="numeric"):
            TissueSegmenter(
                tiles=(),
                threshold="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="s"),
            )

    def test_rejects_out_of_range_threshold(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            TissueSegmenter(
                tiles=(),
                threshold=1.5,
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_tile_tuple(self) -> None:
        tiles = (WSITile(slide_id="S", tile_x=0, tile_y=0, level=0, width=512, height=512),)
        with Tapestry() as t:
            TissueSegmenter(
                tiles=tiles,
                threshold=0.5,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, tuple)
        assert all(isinstance(x, WSITile) for x in out)
