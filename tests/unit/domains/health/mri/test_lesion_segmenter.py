"""Unit tests for :class:`LesionSegmenter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.lesion_segmenter import LesionSegmenter
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            LesionSegmenter(
                nifti_path="",
                model_name="m",
                output_segmentation_path="out",
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_segmentation_path(self) -> None:
        with Tapestry() as t:
            LesionSegmenter(
                nifti_path="in.nii.gz",
                model_name="nnunet",
                output_segmentation_path="seg.nii.gz",
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["s"] == "seg.nii.gz"
