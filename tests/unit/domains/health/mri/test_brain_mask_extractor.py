"""Unit tests for :class:`BrainMaskExtractor`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.brain_mask_extractor import BrainMaskExtractor

_CFG = KnotConfig(id="b")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BrainMaskExtractor:
        return BrainMaskExtractor(nifti_path="in.nii.gz", output_mask_path="mask.nii.gz", _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", output_mask_path="mask.nii.gz")

    async def test_returns_mask_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(nifti_path="in.nii.gz", output_mask_path="mask.nii.gz")
        assert out == "mask.nii.gz"
