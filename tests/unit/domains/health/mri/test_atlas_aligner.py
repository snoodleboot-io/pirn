"""Unit tests for :class:`AtlasAligner`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.atlas_aligner import AtlasAligner

_CFG = KnotConfig(id="a")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> AtlasAligner:
        return AtlasAligner(nifti_path="in.nii.gz", atlas_name="MNI152", output_aligned_path="out.nii.gz", _config=_CFG)

    async def test_rejects_empty_nifti(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", atlas_name="MNI152", output_aligned_path="out.nii.gz")

    async def test_returns_aligned_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(nifti_path="in.nii.gz", atlas_name="MNI152", output_aligned_path="out.nii.gz")
        assert out == "out.nii.gz"
