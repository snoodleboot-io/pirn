"""Unit tests for :class:`WhiteMatterAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.white_matter_analyzer import WhiteMatterAnalyzer
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_path(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            WhiteMatterAnalyzer(
                dwi_nifti_path="",
                bvec_path="b",
                bval_path="v",
                tracts=[],
                _config=KnotConfig(id="w"),
            )

    def test_rejects_non_sequence_tracts(self) -> None:
        with pytest.raises(TypeError, match="tracts"):
            WhiteMatterAnalyzer(
                dwi_nifti_path="x",
                bvec_path="b",
                bval_path="v",
                tracts=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="w"),
            )

    def test_rejects_non_string_tract(self) -> None:
        with pytest.raises(TypeError, match="string"):
            WhiteMatterAnalyzer(
                dwi_nifti_path="x",
                bvec_path="b",
                bval_path="v",
                tracts=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="w"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_per_tract_mapping(self) -> None:
        with Tapestry() as t:
            WhiteMatterAnalyzer(
                dwi_nifti_path="x.nii",
                bvec_path="b",
                bval_path="v",
                tracts=["cc"],
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, Mapping)
        assert "cc" in out
        assert "fa" in out["cc"]
