"""Unit tests for :class:`BrainMaskExtractor`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_health.health_optional_dependency import HealthOptionalDependency
from pirn_health.mri.brain_mask_extractor import BrainMaskExtractor

_CFG = KnotConfig(id="b")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BrainMaskExtractor:
        return BrainMaskExtractor(
            nifti_path="in.nii.gz", output_mask_path="mask.nii.gz", _config=_CFG
        )

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", output_mask_path="mask.nii.gz")

    async def test_returns_mask_path(self) -> None:
        knot = self._make_knot()
        mock_img = MagicMock()
        mock_img.dataobj = np.zeros((4, 4, 4))
        mock_img.affine = np.eye(4)
        mock_img.header = MagicMock()

        mock_nib = MagicMock()
        mock_nib.load.return_value = mock_img

        mock_median_otsu = MagicMock(
            return_value=(np.zeros((4, 4, 4)), np.zeros((4, 4, 4), dtype=bool))
        )

        modules = {
            "nibabel": mock_nib,
            "dipy.segment.mask": MagicMock(median_otsu=mock_median_otsu),
        }

        with patch.object(
            HealthOptionalDependency,
            "require",
            side_effect=lambda module, **_: modules[module],
        ):
            out = await knot.process(nifti_path="in.nii.gz", output_mask_path="mask.nii.gz")
        assert out == "mask.nii.gz"
        mock_median_otsu.assert_called_once()

    async def test_raises_without_dipy(self) -> None:
        knot = self._make_knot()
        with patch.dict(sys.modules, {"dipy.segment.mask": None}):
            with self.assertRaisesRegex(ImportError, "pirn-health\\[mri\\]"):
                await knot.process(nifti_path="in.nii.gz", output_mask_path="mask.nii.gz")
