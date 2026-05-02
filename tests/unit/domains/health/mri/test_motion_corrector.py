"""Unit tests for :class:`MotionCorrector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.motion_corrector import MotionCorrector
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            MotionCorrector(
                nifti_path="",
                output_nifti_path="out",
                _config=KnotConfig(id="m"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_corrected_path(self) -> None:
        with Tapestry() as t:
            MotionCorrector(
                nifti_path="in.nii.gz",
                output_nifti_path="mc.nii.gz",
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["m"] == "mc.nii.gz"
