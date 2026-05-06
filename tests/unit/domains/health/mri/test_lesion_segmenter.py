"""Unit tests for :class:`LesionSegmenter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.lesion_segmenter import LesionSegmenter

_CFG = KnotConfig(id="s")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LesionSegmenter:
        return LesionSegmenter(nifti_path="in.nii.gz", model_name="nnunet", output_segmentation_path="seg.nii.gz", _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", model_name="m", output_segmentation_path="out")

    async def test_returns_segmentation_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(nifti_path="in.nii.gz", model_name="nnunet", output_segmentation_path="seg.nii.gz")
        assert out == "seg.nii.gz"
