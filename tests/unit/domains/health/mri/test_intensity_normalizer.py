"""Unit tests for :class:`IntensityNormalizer`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.intensity_normalizer import IntensityNormalizer

_CFG = KnotConfig(id="n")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> IntensityNormalizer:
        return IntensityNormalizer(nifti_path="in.nii.gz", method="zscore", output_nifti_path="norm.nii.gz", _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", method="zscore", output_nifti_path="out")

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(nifti_path="x", method="bogus", output_nifti_path="out")

    async def test_returns_normalised_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(nifti_path="in.nii.gz", method="zscore", output_nifti_path="norm.nii.gz")
        assert out == "norm.nii.gz"
