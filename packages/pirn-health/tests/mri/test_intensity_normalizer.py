"""Unit tests for :class:`IntensityNormalizer`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_health.mri.intensity_normalizer import IntensityNormalizer

_CFG = KnotConfig(id="n")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> IntensityNormalizer:
        return IntensityNormalizer(
            nifti_path="in.nii.gz", method="zscore", output_nifti_path="norm.nii.gz", _config=_CFG
        )

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", method="zscore", output_nifti_path="out")

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(nifti_path="x", method="bogus", output_nifti_path="out")

    async def test_returns_normalized_path(self) -> None:
        knot = self._make_knot()
        mock_nib = MagicMock()
        mock_img = MagicMock()
        mock_img.dataobj = [[1.0, 2.0], [3.0, 4.0]]
        mock_img.affine = None
        mock_img.header = None
        mock_nib.load.return_value = mock_img
        mock_nib.Nifti1Image.return_value = MagicMock()
        with patch.object(
            OptionalDependency,
            "require",
            side_effect=lambda module, **_: {"nibabel": mock_nib}[module],
        ):
            out = await knot.process(
                nifti_path="in.nii.gz", method="zscore", output_nifti_path="out.nii.gz"
            )
        assert out == "out.nii.gz"
        mock_nib.save.assert_called_once()

    async def test_raises_without_nibabel(self) -> None:
        knot = self._make_knot()
        with patch.dict(sys.modules, {"nibabel": None}):
            with self.assertRaisesRegex(ImportError, "pirn-health\\[mri\\]"):
                await knot.process(
                    nifti_path="in.nii.gz", method="zscore", output_nifti_path="out.nii.gz"
                )
