"""Unit tests for :class:`AtlasAligner`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.atlas_aligner import AtlasAligner
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_nifti(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            AtlasAligner(
                nifti_path="",
                atlas_name="MNI152",
                output_aligned_path="out",
                _config=KnotConfig(id="a"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_aligned_path(self) -> None:
        with Tapestry() as t:
            AtlasAligner(
                nifti_path="in.nii.gz",
                atlas_name="MNI152",
                output_aligned_path="out.nii.gz",
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["a"] == "out.nii.gz"
