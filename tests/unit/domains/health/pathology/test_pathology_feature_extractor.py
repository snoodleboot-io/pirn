"""Unit tests for :class:`PathologyFeatureExtractor`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.cell_detector import CellDetector
from pirn.domains.health.pathology.mitosis_counter import MitosisCounter
from pirn.domains.health.pathology.pathology_feature_extractor import (
    PathologyFeatureExtractor,
)
from pirn.domains.health.types.wsi_tile import WSITile
from pirn.tapestry import Tapestry


@knot
async def emit_cell_counts() -> Mapping[tuple[int, int], int]:
    return {(0, 0): 10, (0, 512): 4}


@knot
async def emit_mitosis_total() -> int:
    return 6


class TestConstruction:
    def test_rejects_non_knot_cell_counts(self) -> None:
        with Tapestry():
            mitosis = emit_mitosis_total(_config=KnotConfig(id="m"))
            with pytest.raises(TypeError, match="cell_counts"):
                PathologyFeatureExtractor(
                    cell_counts="not-a-knot",  # type: ignore[arg-type]
                    mitosis_counts=mitosis,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_non_knot_mitosis_counts(self) -> None:
        with Tapestry():
            cells = emit_cell_counts(_config=KnotConfig(id="c"))
            with pytest.raises(TypeError, match="mitosis_counts"):
                PathologyFeatureExtractor(
                    cell_counts=cells,
                    mitosis_counts=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_missing_cell_counts(self) -> None:
        with Tapestry():
            mitosis = emit_mitosis_total(_config=KnotConfig(id="m"))
            with pytest.raises(TypeError, match="cell_counts"):
                PathologyFeatureExtractor(
                    mitosis_counts=mitosis,  # type: ignore[call-arg]
                    _config=KnotConfig(id="f"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_per_tile_features(self) -> None:
        tiles = (
            WSITile(slide_id="S", tile_x=0, tile_y=0, level=0, width=512, height=512),
            WSITile(slide_id="S", tile_x=0, tile_y=512, level=0, width=512, height=512),
        )
        with Tapestry() as t:
            cells = CellDetector(
                tiles=tiles,
                model_name="stardist",
                _config=KnotConfig(id="cells"),
            )
            mitosis = MitosisCounter(
                tiles=tiles,
                confidence_threshold=0.5,
                _config=KnotConfig(id="mitosis"),
            )
            PathologyFeatureExtractor(
                cell_counts=cells,
                mitosis_counts=mitosis,
                _config=KnotConfig(id="features"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["features"]
        assert isinstance(out, Mapping)
        # CellDetector returns 0s, MitosisCounter returns 0; densities = 0.
        assert (0, 0) in out
        assert (0, 512) in out
        for position, vector in out.items():
            assert vector["cell_count"] == 0
            assert vector["mitosis_count"] == 0
            assert vector["mitosis_density"] == 0.0

    async def test_density_with_stub_upstreams(self) -> None:
        with Tapestry() as t:
            cells = emit_cell_counts(_config=KnotConfig(id="cells"))
            mitosis = emit_mitosis_total(_config=KnotConfig(id="mitosis"))
            PathologyFeatureExtractor(
                cell_counts=cells,
                mitosis_counts=mitosis,
                _config=KnotConfig(id="features"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["features"]
        assert isinstance(out, Mapping)
        # 6 mitosis split across 2 tiles -> 3 each; cell_count=10 -> density 0.3
        assert out[(0, 0)]["cell_count"] == 10
        assert out[(0, 0)]["mitosis_count"] == 3
        assert out[(0, 0)]["mitosis_density"] == pytest.approx(0.3)
        assert out[(0, 512)]["cell_count"] == 4
        assert out[(0, 512)]["mitosis_count"] == 3
        assert out[(0, 512)]["mitosis_density"] == pytest.approx(0.75)
