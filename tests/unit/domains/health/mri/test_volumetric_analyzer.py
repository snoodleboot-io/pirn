"""Unit tests for :class:`VolumetricAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.volumetric_analyzer import VolumetricAnalyzer
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_path(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            VolumetricAnalyzer(
                labelled_nifti_path="",
                regions=[],
                _config=KnotConfig(id="v"),
            )

    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="regions"):
            VolumetricAnalyzer(
                labelled_nifti_path="x",
                regions=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="v"),
            )

    def test_rejects_non_string_region(self) -> None:
        with pytest.raises(TypeError, match="string"):
            VolumetricAnalyzer(
                labelled_nifti_path="x",
                regions=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="v"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_per_region_mapping(self) -> None:
        with Tapestry() as t:
            VolumetricAnalyzer(
                labelled_nifti_path="x",
                regions=["frontal"],
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["v"]
        assert isinstance(out, Mapping)
        assert "frontal" in out
