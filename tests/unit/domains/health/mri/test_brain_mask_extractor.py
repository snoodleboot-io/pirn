"""Unit tests for :class:`BrainMaskExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.brain_mask_extractor import BrainMaskExtractor
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            BrainMaskExtractor(
                nifti_path="",
                output_mask_path="out",
                _config=KnotConfig(id="b"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_mask_path(self) -> None:
        with Tapestry() as t:
            BrainMaskExtractor(
                nifti_path="in.nii.gz",
                output_mask_path="mask.nii.gz",
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["b"] == "mask.nii.gz"
