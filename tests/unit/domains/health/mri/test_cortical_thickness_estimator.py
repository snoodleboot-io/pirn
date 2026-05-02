"""Unit tests for :class:`CorticalThicknessEstimator`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.cortical_thickness_estimator import (
    CorticalThicknessEstimator,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_path(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            CorticalThicknessEstimator(
                t1_nifti_path="",
                regions=[],
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="regions"):
            CorticalThicknessEstimator(
                t1_nifti_path="x",
                regions=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_string_region(self) -> None:
        with pytest.raises(TypeError, match="string"):
            CorticalThicknessEstimator(
                t1_nifti_path="x",
                regions=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="c"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_per_region_mapping(self) -> None:
        with Tapestry() as t:
            CorticalThicknessEstimator(
                t1_nifti_path="x",
                regions=["frontal", "parietal"],
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {"frontal", "parietal"}
